"""Two distinct power/sample-size calculations for the full-scale study.
Previously the plan asserted N~150-300 without justification, conflating
two different quantities. This script computes both properly, grounded in
real pilot data (data/results/static_audit_v1.json,
experiments/mistral-template-test/pilot_results.json /
pilot_2x2_results.json) rather than an arbitrary guess.

1. Corpus size for estimating overall divergence PREVALENCE within a target
   margin of error (single-proportion sample size formula).
2. Prompts per flagged anomaly for behavioral-confirmation statistical POWER
   (two-proportion comparison via Cohen's h).

Run: python3 scripts/power_calculations.py
"""

from __future__ import annotations

from math import asin, sqrt

Z_95 = 1.959964  # two-sided 95% confidence
Z_POWER_80 = 0.841621  # 80% power
Z_POWER_90 = 1.281552  # 90% power


def corpus_size_for_prevalence_margin(p: float, margin: float, z: float = Z_95) -> float:
    """n = z^2 * p*(1-p) / margin^2 -- single-proportion sample size."""
    return (z**2 * p * (1 - p)) / margin**2


def cohens_h(p1: float, p2: float) -> float:
    return 2 * asin(sqrt(p2)) - 2 * asin(sqrt(p1))


def n_per_group_two_proportion(h: float, z_alpha: float = Z_95, z_beta: float = Z_POWER_80) -> float:
    """n per condition for a two-proportion comparison at the given power."""
    return ((z_alpha + z_beta) / h) ** 2


def main():
    print("=== 1. Corpus size for prevalence-estimate precision (95% CI) ===")
    p_observed = 8 / 35  # actual observed rate: static_audit_v1.json, 8/35 repos diverge from anchor's modal template
    p_conservative = 0.5
    print(f"observed pilot divergence rate: {p_observed:.3f} (8/35 repos, from static_audit_v1.json)")
    for margin_pct in (10, 7, 5):
        margin = margin_pct / 100
        n_obs = corpus_size_for_prevalence_margin(p_observed, margin)
        n_cons = corpus_size_for_prevalence_margin(p_conservative, margin)
        print(f"  margin=+/-{margin_pct}pp: n={n_obs:.0f} (observed p={p_observed:.2f}), "
              f"n={n_cons:.0f} (conservative p=0.5)")

    print()
    print("=== 2. Prompts per flagged anomaly for behavioral confirmation (Cohen's h) ===")
    p1, p2_observed = 0.476, 0.667  # this pilot's own Condition A / B refusal rates
    h_obs = cohens_h(p1, p2_observed)
    print(f"observed pilot effect: p1={p1}, p2={p2_observed}, Cohen's h={h_obs:.3f} "
          f"-> n per condition (80% power) = {n_per_group_two_proportion(h_obs):.0f}")
    print("(caveat: using a small pilot's own observed effect to size itself is optimistic --")
    print(" small-pilot point estimates tend to be upwardly biased. See table below for a range.)")
    print()
    for target_pp in (19, 15, 10, 5):
        p2 = p1 + target_pp / 100
        h = cohens_h(p1, p2)
        n80 = n_per_group_two_proportion(h, z_beta=Z_POWER_80)
        n90 = n_per_group_two_proportion(h, z_beta=Z_POWER_90)
        print(f"  target effect={target_pp}pp: h={h:.3f}, n/condition (80% power)={n80:.0f}, "
              f"(90% power)={n90:.0f}")


if __name__ == "__main__":
    main()
