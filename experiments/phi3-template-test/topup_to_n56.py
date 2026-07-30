"""Scale the Phi-3 Stage-2 pilot from n=21 to n=56 per condition, same
rationale and method as the Mistral topup (experiments/mistral-template
-test/topup_to_n56.py) -- see that file's docstring for the power-calc
justification. Phi-3's original pilot already ran the full 3-condition
design in one pass, so the merge here is simpler than Mistral's (which
had two separate result files).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_pilot_2x2 import (  # noqa: E402
    SAFETY_SYSTEM_PROMPT,
    classify,
    generate,
    load_harmbench_subset,
    render_no_system,
    render_with_system,
)


def main():
    modal = Path("modal_template.jinja").read_text()
    minority = Path("minority_template.jinja").read_text()

    old_subset = load_harmbench_subset(n_per_category=3)
    full_subset = load_harmbench_subset(n_per_category=8)
    old_prompts = {x["prompt"] for x in old_subset}
    topup = [x for x in full_subset if x["prompt"] not in old_prompts]
    print(f"Running {len(topup)} NEW prompts x 3 conditions = {len(topup) * 3} generations", file=sys.stderr)

    new_results = []
    for i, item in enumerate(topup):
        prompt = item["prompt"]
        print(f"[{i + 1}/{len(topup)}] ({item['category']}) {prompt[:60]}", file=sys.stderr)

        rendered_a = render_no_system(prompt, minority)
        out_a = generate(rendered_a)
        refuse_a = classify(out_a)

        rendered_b = render_with_system(prompt, SAFETY_SYSTEM_PROMPT, modal)
        out_b = generate(rendered_b)
        refuse_b = classify(out_b)

        rendered_c = render_no_system(prompt, modal)
        out_c = generate(rendered_c)
        refuse_c = classify(out_c)

        new_results.append({
            "category": item["category"], "prompt": prompt,
            "condition_a_minority_no_system_refused": refuse_a,
            "condition_b_modal_with_system_refused": refuse_b,
            "condition_c_modal_no_system_refused": refuse_c,
        })
        time.sleep(0.1)

    old = json.loads(Path("pilot_2x2_results.json").read_text())["results"]
    combined = [
        {
            "category": r["category"], "prompt": r["prompt"],
            "condition_a_minority_no_system_refused": r["condition_a_minority_no_system_refused"],
            "condition_b_modal_with_system_refused": r["condition_b_modal_with_system_refused"],
            "condition_c_modal_no_system_refused": r["condition_c_modal_no_system_refused"],
        }
        for r in old
    ] + new_results

    n = len(combined)
    a_rate = sum(r["condition_a_minority_no_system_refused"] for r in combined) / n
    b_rate = sum(r["condition_b_modal_with_system_refused"] for r in combined) / n
    c_rate = sum(r["condition_c_modal_no_system_refused"] for r in combined) / n

    summary = {
        "n_prompts": n,
        "condition_a_minority_no_system": a_rate,
        "condition_b_modal_with_system": b_rate,
        "condition_c_modal_no_system": c_rate,
        "content_effect_B_minus_C_pp": (b_rate - c_rate) * 100,
        "template_shape_effect_A_minus_C_pp": (a_rate - c_rate) * 100,
        "combined_real_world_effect_A_minus_B_pp": (a_rate - b_rate) * 100,
    }
    print("\n=== N=56 SUMMARY ===", file=sys.stderr)
    print(json.dumps(summary, indent=2), file=sys.stderr)

    Path("pilot_n56_results.json").write_text(json.dumps({"summary": summary, "results": combined}, indent=2))
    Path("topup_new_results.json").write_text(json.dumps(new_results, indent=2))


if __name__ == "__main__":
    main()
