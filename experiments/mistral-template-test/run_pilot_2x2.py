"""Stage-2 pilot, extended: adds the missing control arm the first pilot
lacked, to separate two effects that were confounded together in the
original A-vs-B comparison:

  (1) does DELIVERING the safety system-prompt CONTENT increase refusal,
      holding the template's rendering shape constant?
  (2) does the template's rendering SHAPE alone (bracket/whitespace/
      structure differences between publishers) shift refusal, holding
      system-prompt-presence constant?

True 2x2 would be {popular, longtail} x {no_system, with_system}, but
popular x with_system is structurally undefined -- that template's own
Jinja logic raises an exception on any system-role message, so there is
no "popular + system" condition to render. This is itself a real finding,
not a gap in the design: one cell of the factorial is categorically
impossible for that template family.

So the actual (necessarily incomplete) design has three cells:
  A. popular,  no_system   -- already run in run_pilot.py (47.6%, n=21)
  B. longtail, with_system -- already run in run_pilot.py (66.7%, n=21)
  C. longtail, no_system   -- NEW, run here

Comparisons:
  B vs C -> isolates the system-prompt-CONTENT effect (template held constant)
  A vs C -> isolates the template-rendering-SHAPE effect (system-prompt-presence
            held constant at "none")
  A vs B -> the original real-world-consequence comparison (both effects
            combined, i.e. what actually happens to a user who pulls one
            repo vs. the other)

Reuses the exact same 21-prompt stratified subsample, classifier, and
mistral:7b weights as run_pilot.py for a clean comparison.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from run_pilot import classify, generate, load_harmbench_subset, render_no_system


def main():
    longtail_template = Path("longtail_template.jinja").read_text()

    subset = load_harmbench_subset(n_per_category=3)
    print(f"Condition C: {len(subset)} prompts, longtail template, no system prompt", file=sys.stderr)

    results = []
    for i, item in enumerate(subset):
        prompt = item["prompt"]
        print(f"[{i + 1}/{len(subset)}] ({item['category']}) {prompt[:60]}", file=sys.stderr)

        rendered_c = render_no_system(prompt, longtail_template)
        out_c = generate(rendered_c)
        refuse_c = classify(out_c)

        results.append({
            "category": item["category"],
            "prompt": prompt,
            "condition_c_longtail_no_system_refused": refuse_c,
            "condition_c_output": out_c,
        })
        time.sleep(0.1)

    n = len(results)
    c_refuse_rate = sum(r["condition_c_longtail_no_system_refused"] for r in results) / n

    # Load the original A/B results to compute the full three-way comparison.
    orig = json.loads(Path("pilot_results.json").read_text())
    a_rate = orig["summary"]["condition_a_no_system_refuse_rate"]
    b_rate = orig["summary"]["condition_b_with_system_refuse_rate"]

    summary = {
        "n_prompts": n,
        "condition_a_popular_no_system": a_rate,
        "condition_b_longtail_with_system": b_rate,
        "condition_c_longtail_no_system": c_refuse_rate,
        "content_effect_B_minus_C_pp": (b_rate - c_refuse_rate) * 100,
        "template_shape_effect_A_minus_C_pp": (a_rate - c_refuse_rate) * 100,
        "combined_real_world_effect_A_minus_B_pp": (a_rate - b_rate) * 100,
    }
    print("\n=== 2x2 SUMMARY ===", file=sys.stderr)
    print(json.dumps(summary, indent=2), file=sys.stderr)

    Path("pilot_2x2_results.json").write_text(
        json.dumps({"summary": summary, "condition_c_results": results}, indent=2)
    )


if __name__ == "__main__":
    main()
