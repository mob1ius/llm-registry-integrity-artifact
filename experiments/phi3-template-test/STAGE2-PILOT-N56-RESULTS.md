phi-3, scaled to n=56

Same rationale as the mistral scale-up (see
experiments/mistral-template-test/STAGE2-PILOT-N56-RESULTS.md): n=21 was
below every power-calc target, scaled to n=56 with the same 35-new-prompt
approach.

| Condition | n=21 | n=56 | 95% CI (n=56) |
|---|---|---|---|
| A -- minority template, no system | 81.0% | 76.8% (43/56) | [64.2, 85.9] |
| B -- modal template, with system | 95.2% | 87.5% (49/56) | [76.4, 93.8] |
| C -- modal template, no system | 81.0% | 82.1% (46/56) | [70.2, 90.0] |

Content effect (B-C): +5.4pp (was +14.3pp -- smaller, not larger)
Shape effect (A-C): -5.4pp (was 0.0pp)
Combined (A-B): -10.7pp (was -14.3pp)

Different outcome from Mistral, reporting it straight. All three CIs
heavily overlap at n=56. Content effect is still statistically
indistinguishable from noise, and the point estimate actually shrank
with more data (14.3 -> 5.4) instead of growing like Mistral's did.

This is a real outcome, not a failure of the method. Phi-3's baseline is
already high (76-87% across conditions) -- way less headroom than
Mistral's (37-73%). Per the power table, a 5-10pp effect needs
n~195-784, not 56 -- that target was sized for the ~15-19pp effects the
n=21 pilots suggested, which was right for Mistral and was never going to
be enough for Phi-3's smaller, ceiling-adjacent effect.

So the two anchors with real (non-ceiling) effects diverge in how
confirmed they are: Mistral's content effect is statistically confirmed
at n=56. Phi-3's is real and mechanistically explained (causal direction
still holds against canonical) but stays an underpowered point estimate
even at n=56. Worth stating plainly rather than blending into one "both
anchors confirm it" line -- Phi-3 demonstrates the mechanism, only
Mistral currently confirms the magnitude statistically.
