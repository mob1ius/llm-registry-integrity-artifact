Stage-2 pilot, Mistral

Point of this pilot: before sinking time into the full-scale audit, need
to know whether static template divergence actually translates into a
safety-behavior difference, or just a formatting difference nobody cares
about.

The static audit found a real split in Mistral-7B-Instruct-v0.3 GGUF
templates by publisher. High-popularity repos (MaziyarPanahi,
lmstudio-community, SanctumAI) ship a minimal template with no
system-role handling at all -- it raises an exception on anything that
isn't user/assistant. Confirmed by hand: rendering a system+user pair
throws `ValueError: Conversation roles must alternate...` before
producing anything. Long-tail repos (NonMiFrega, EnlistedGhost, tokoin)
have the newer, complete template that properly folds a system message
into the INST block.

Real consequence: any caller that doesn't special-case this (most don't)
gets a safety system prompt that just can't be delivered through the
popular template family. Not delivered differently -- dropped. That's
what this tests.

Method: same weights throughout (locally-pulled mistral:7b via Ollama,
raw-generate mode so Ollama's own templating layer is bypassed entirely
and the exact rendered string goes out as-is). HarmBench Standard set,
140 prompts, stratified subsample of 3 x 7 categories = 21 for this
pilot. A self-contained REFUSE/COMPLY heuristic classifier.

- Condition A (no_system): user prompt only, rendered via the popular
  template.
- Condition B (with_system): safety prompt + user prompt, rendered via
  the long-tail template.

Result:

| Condition | Refused | Rate | 95% CI |
|---|---|---|---|
| A -- no system (popular template) | 10/21 | 47.6% | [28.3, 67.6] |
| B -- system delivered (long-tail template) | 14/21 | 66.7% | [45.4, 82.8] |

Delta: +19.0pp, right direction.

The point estimate is real and mechanistically explained, not a fluke of
classifier quirks or template syntax -- static divergence *can* translate
into a measurable behavior difference on identical weights, not just a
formatting difference. But the CIs overlap at n=21 ([28.3,67.6] vs
[45.4,82.8]) -- not yet distinguishable from noise at conventional
thresholds. Underpowered, not null. Calling it "proven" at this stage
would be the exact kind of overclaim to avoid.

## Adding a control arm

The original A-vs-B comparison confounds two things: whether the safety
content actually got delivered, and whether the two templates just
render structurally different prompt shapes for unrelated reasons.
Added a third condition, same 21 prompts, same classifier, same weights:

- C -- long-tail template, no system prompt (isolates shape alone, same
  template as B minus the content)

| Condition | Refused | Rate | 95% CI |
|---|---|---|---|
| A -- popular, no system | 10/21 | 47.6% | [28.3, 67.6] |
| B -- long-tail, with system | 14/21 | 66.7% | [45.4, 82.8] |
| C -- long-tail, no system | 9/21 | 42.9% | [24.5, 63.5] |

Content effect (B-C): +23.8pp -- almost all of the real effect lives
here.
Shape effect (A-C): +4.8pp -- small, well inside overlapping CIs
([28.3,67.6] vs [24.5,63.5], basically noise).
Combined (A-B): -19.0pp, and the arithmetic checks out: (A-C)-(B-C) =
4.8-23.8 = -19.0, matches the original number exactly.

So the real-world effect is almost entirely about whether the safety
instruction reaches the model at all, not incidental formatting
differences between publishers. Good sign for the core mechanism -- it's
what we think it is, not template-syntax noise. All three conditions
still overlap pairwise at n=21; this pilot establishes the mechanism and
its decomposition, not statistical significance yet. That's the right
job for a pilot at this stage.

## Power calculations for scaling up

Two different questions got conflated under one guessed number
(N~150-300) earlier. Worked both out properly from this pilot's actual
data.

Corpus size, for prevalence with a target margin:
`n = z^2 * p(1-p) / E^2`, using the actual observed rate (8/35 = 22.9%
diverge from modal, from the full static audit):

| margin | n at p=0.229 | n at p=0.5 |
|---|---|---|
| +/-10pp | 68 | 96 |
| +/-7pp | 138 | 196 |
| +/-5pp | 271 | 384 |

The earlier N~150-300 guess lands almost exactly on the +/-7pp target
(138) and comfortably covers the conservative case at the same margin
(196). Turns out the guess was fine, but now there's a real number behind
it. Target N=150-200 for +/-7pp.

Prompts per anomaly, for behavioral power. Cohen's h, two-proportion,
80%/95%:

| assumed effect | h | n (80%) | n (90%) |
|---|---|---|---|
| 19pp (this pilot) | 0.386 | 53 | 70 |
| 15pp | 0.303 | 86 | 115 |
| 10pp | 0.201 | 195 | 261 |
| 5pp | 0.100 | 784 | 1050 |

Using a pilot's own observed effect to size itself is optimistic -- small
pilots run hot. Budget n=50-100 per condition per anomaly as the default
(covers effects >=15pp), with an explicit limitation that anything
<=10pp needs n>=195 and won't show up reliably at the default budget.

So: this pilot justifies moving to the full-scale audit, with a real
mechanism, a working protocol, and justified rather than guessed targets
(N=150-200 corpus, n=50-100 per flagged anomaly).

## Canonical check, after the fact

One more thing worth checking: this pilot's template arms were chosen
from the earlier N=40 pilot's popularity buckets, not verified against
the actual developer-canonical template. In principle the causal
direction could be backwards if the "popular" template happened to be
the correct one.

Checked directly. Fetched mistralai/Mistral-7B-Instruct-v0.3's canonical
template (ungated, 200). The pilot's "system-delivered" arm
(longtail_template.jinja) matches canonical exactly (e16746b4...); the
"no-system" arm (popular_template.jinja, MaziyarPanahi/
lmstudio-community/SanctumAI) diverges (26a59556...). No inversion --
direction is correct and now verified, not assumed. Detail in
data/results/CANONICAL-DIVERGENCE-RESULTS.md.
