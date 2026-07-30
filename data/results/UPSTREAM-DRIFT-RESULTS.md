# Upstream drift

A review pass flagged that the fourth threat category (upstream
checkpoint/template drift -- the developer revises their own template over
time, and old quantizations then look "divergent" for reasons that have
nothing to do with the publisher) was in the writeup as text but never
actually checked against data. This closes that using
`scripts/upstream_drift_check.py`.

Method: use HF's `createdAt` on each corpus repo as a proxy for when the
quantization was made. Compare the earliest `createdAt` among repos
matching the modal/canonical template against the `createdAt` of every
divergent repo. If a divergent repo predates the earliest correct-template
repo, staleness is a plausible explanation -- the correct template might
not have existed yet.

Caveat: `createdAt`/`lastModified` are repo-level, not specific to the
`chat_template` file's own history. This is a proxy, not a precise
file-level audit. A tighter version would check `tokenizer_config.json`'s
own commit history directly -- didn't do that here, ran out of time.

## Result

| Anchor | Divergent repos w/ timestamp | Predate earliest modal repo | % explainable by staleness |
|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 18 | 16 | 88.9% |
| Llama-3.1-8B-Instruct | 13 | 0 | 0.0% |
| Qwen2.5-7B-Instruct | 4 | 0 | 0.0% |
| gemma-2-9b-it | 3 | 0 | 0.0% |
| Phi-3-mini-4k-instruct | 8 | 0 | 0.0% |

Mistral is the outlier -- and it's the anchor with the biggest behavioral
effect. 16 of its 18 divergent (no-system-role) repos were created before
the earliest repo with the correct (system-role-aware) template. Reads
like a real historical event: Mistral's official template got revised to
add system-role handling at some point, and a chunk of the popular
quantizations predate that and were never reissued.

For the other four, staleness explains 0% -- every divergent repo
postdates the correct template's earliest appearance. So for those, the
correct template really was available and the publisher just didn't use
it.

What this changes: not the static divergence number, not the behavioral
effect, not the causal-direction check -- a stale template still fails to
deliver the safety instruction regardless of why it's stale. What it does
change is the framing for Mistral specifically. "Popular quantizers were
negligent" isn't the accurate story there. "The ecosystem is slow to
propagate a template revision, and the popular repos are disproportionately
old ones" is. That's a different, more useful finding -- it points at
registry-side staleness detection as the fix, not publisher blame. For
the other four anchors, "publisher chose not to match an available
correct template" still holds, now checked instead of assumed.

Report this per-anchor, not pooled. For Mistral, lead with staleness as
the explanation and frame the practitioner recommendation around
surfacing staleness, not blaming publishers. For the rest, the original
framing stands.
