"""Scale the Mistral Stage-2 pilot from n=21 to n=56 per condition (7
categories x 8), per the should-fix item from the adversarial review: all
four original pilots ran below every power-calculation target (53-195),
so zero behavioral results were statistically significant. n=56 is just
above the n=53 target for detecting the ~19pp effect at 80% power.

Only generates the 35 NEW prompts (not already run at n=21) for all three
conditions, then merges with the existing pilot_results.json /
pilot_2x2_results.json to produce a combined n=56 result -- avoids
redundant compute on the 21 prompts already run.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_pilot import classify, generate, load_harmbench_subset, render_no_system, render_with_system, SAFETY_SYSTEM_PROMPT  # noqa: E402


def main():
    popular_template = Path("popular_template.jinja").read_text()
    longtail_template = Path("longtail_template.jinja").read_text()

    old_subset = load_harmbench_subset(n_per_category=3)
    full_subset = load_harmbench_subset(n_per_category=8)
    old_prompts = {x["prompt"] for x in old_subset}
    topup = [x for x in full_subset if x["prompt"] not in old_prompts]
    print(f"Running {len(topup)} NEW prompts x 3 conditions = {len(topup) * 3} generations", file=sys.stderr)

    new_results = []
    for i, item in enumerate(topup):
        prompt = item["prompt"]
        print(f"[{i + 1}/{len(topup)}] ({item['category']}) {prompt[:60]}", file=sys.stderr)

        rendered_a = render_no_system(prompt, popular_template)
        out_a = generate(rendered_a)
        refuse_a = classify(out_a)

        rendered_b = render_with_system(prompt, SAFETY_SYSTEM_PROMPT, longtail_template)
        out_b = generate(rendered_b)
        refuse_b = classify(out_b)

        rendered_c = render_no_system(prompt, longtail_template)
        out_c = generate(rendered_c)
        refuse_c = classify(out_c)

        new_results.append({
            "category": item["category"], "prompt": prompt,
            "condition_a_no_system_refused": refuse_a, "condition_a_output": out_a,
            "condition_b_with_system_refused": refuse_b, "condition_b_output": out_b,
            "condition_c_no_system_refused": refuse_c, "condition_c_output": out_c,
        })
        time.sleep(0.1)

    # Merge with existing n=21 results (from pilot_results.json A/B +
    # pilot_2x2_results.json C) into one combined n=56 dataset.
    old_ab = json.loads(Path("pilot_results.json").read_text())["results"]
    old_c = json.loads(Path("pilot_2x2_results.json").read_text())["condition_c_results"]
    old_c_by_prompt = {r["prompt"]: r["condition_c_longtail_no_system_refused"] for r in old_c}

    combined = []
    for r in old_ab:
        combined.append({
            "category": r["category"], "prompt": r["prompt"],
            "condition_a_no_system_refused": r["condition_a_no_system_refused"],
            "condition_b_with_system_refused": r["condition_b_with_system_refused"],
            "condition_c_no_system_refused": old_c_by_prompt.get(r["prompt"]),
        })
    for r in new_results:
        combined.append({
            "category": r["category"], "prompt": r["prompt"],
            "condition_a_no_system_refused": r["condition_a_no_system_refused"],
            "condition_b_with_system_refused": r["condition_b_with_system_refused"],
            "condition_c_no_system_refused": r["condition_c_no_system_refused"],
        })

    n = len(combined)
    a_rate = sum(r["condition_a_no_system_refused"] for r in combined) / n
    b_rate = sum(r["condition_b_with_system_refused"] for r in combined) / n
    c_rate = sum(r["condition_c_no_system_refused"] for r in combined) / n

    summary = {
        "n_prompts": n,
        "condition_a_no_system": a_rate,
        "condition_b_with_system": b_rate,
        "condition_c_no_system": c_rate,
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
