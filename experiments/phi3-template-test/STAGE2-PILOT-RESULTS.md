phi-3 pilot

Goal here: does the Mistral safety-consequence finding hold for a second,
independent model family, or was that a Mistral-specific quirk?

The scaled static audit (N=150) found a real split in Phi-3-mini-4k-instruct
GGUFs -- a modal cluster (27/35 repos, 407 chars, e.g.
bartowski/Phi-3.1-mini-4k-instruct-GGUF) that handles a system-role
message via `<|system|>`, and a minority cluster (6/35, spans both
popularity buckets, 269 chars, e.g.
qwp4w3hyb/Phi-3-mini-4k-instruct-iMat-GGUF) with no system-role branch at
all.

Different failure mode than Mistral, and quieter. Mistral's minority
template threw an exception on a system message -- a loud failure a
developer would probably notice. Phi-3's minority template just silently
renders with the system message dropped, no error at all. Confirmed by
hand: render a system+user pair, the output just doesn't have the system
content in it, nothing flags it.

Method: same protocol as Mistral, same 21-prompt stratified subsample,
same classifier, phi3:3.8b local, Ollama raw-generate. Ran the full
3-condition design in one pass this time (the Mistral pilot needed a
follow-up script to add its third condition):

- A -- minority template, no system
- B -- modal template, with system
- C -- modal template, no system

Result:

| Condition | Refused | Rate | 95% CI |
|---|---|---|---|
| A -- minority, no system | 17/21 | 81.0% | [60.0, 92.3] |
| B -- modal, with system | 20/21 | 95.2% | [77.3, 99.2] |
| C -- modal, no system | 17/21 | 81.0% | [60.0, 92.3] |

Content effect (B-C): +14.3pp
Shape effect (A-C): 0.0pp -- A and C are identical, same point estimate,
not just overlapping CIs. Cleaner than Mistral (which had a small +4.8pp
shape effect) -- 100% of the measured effect here is content delivery,
0% template syntax.
Combined (A-B): -14.3pp, checks out: (A-C)-(B-C) = 0-14.3 = -14.3.

Phi-3's baseline (80.95% with no system) is a lot higher than Mistral's
(42.9%), so less headroom for the content effect to move things. With an
81% baseline the max possible gain is 19pp (to 100%); the observed 14.3pp
uses about 75% of that -- a strong effect relative to available room, not
a marginal one. All three CIs still overlap at n=21, same
underpowered-but-real situation as Mistral. Per the power calc, closing
this needs n~86 per condition for a 15pp effect at 80% power.

## Does it generalize?

| | Mistral | Phi-3 |
|---|---|---|
| Mechanism | exception on system message | silent drop |
| Content effect | +23.8pp | +14.3pp |
| Shape effect | +4.8pp (noise) | 0.0pp (exact null) |
| Combined | -19.0pp | -14.3pp |
| Direction | delivered -> more refusal | delivered -> more refusal |

Yes. Two independent families, different developers, different failure
modes (hard crash vs silent drop), same direction, same qualitative
decomposition -- content effect dominates, shape effect is small to
nothing. Effect sizes differ, which makes sense given different baselines
and different failure modes.

What this doesn't show yet: whether it holds for the other 3 anchors.
Llama-3.1, Qwen2.5, and gemma all show static divergence too but weren't
behaviorally tested at this point. Scope the claim to "2 of 5, same
mechanism" for now, not universal.

## Canonical check

Same check as Mistral. Fetched microsoft/Phi-3-mini-4k-instruct's
canonical template (ungated, 200). The modal/"system-aware" arm matches
canonical exactly (dcaee66d...); the minority/"silent-drop" arm diverges
(268b6082...). No inversion, direction confirmed. See
data/results/CANONICAL-DIVERGENCE-RESULTS.md.
