second registry, for external validity

The primary corpus is built entirely from Hugging Face's search API,
which is a real sampling-bias risk -- a finding built on what one
platform surfaces could just be an artifact of that platform's own
community rather than a property of the GGUF ecosystem generally. Rather
than just note that as a limitation, built an actual second corpus
against ModelScope (modelscope.cn, Alibaba's hub) for the three anchors
with verified canonical ground truth.

`scripts/build_modelscope_corpus.py`. ModelScope's search API
(`PUT /api/v1/dolphin/models`) returns the GGUF chat_template string
directly in the response -- no binary header parsing needed, unlike the
HF side. Canonical templates were re-fetched fresh from each anchor's
ungated HF repo rather than reusing the primary audit's stored hashes, so
this has its own independent ground-truth fetch.

Filtering is weaker here and that's worth saying plainly. ModelScope
doesn't expose a reliable base_model field, so couldn't replicate the
primary corpus's two-stage filter exactly. Instead: require gguf in the
declared libraries; require the repo name to start with the anchor's
exact name; exclude repos whose name (after stripping the prefix)
contains a different-family keyword (vl, coder, 1m, abliterated, math,
vision, omni, audio, embedding) since ModelScope's fuzzy search returns
things like Qwen2.5-VL-7B-Instruct under a Qwen2.5-7B-Instruct search;
apply the same fine-tune-keyword list as before. Weaker than the primary
filter, reported as such.

## Numbers

| Anchor | Raw hits | Excluded | Included | Diverge | % |
|---|---|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 41 | 27 | 14 | 10 | 71.4% |
| Qwen2.5-7B-Instruct | 97 | 79 | 18 | 8 | 44.4% |
| Phi-3-mini-4k-instruct | 26 | 10 | 16 | 11 | 68.8% |
| pooled | 164 | 116 | 48 | 29 | 60.4% |

Exclusion breakdown: 103 variant-family mismatches (the biggest category
by far -- confirms ModelScope's search surfaces a lot of off-target
families a base_model filter would've caught for free), 9 not-gguf, 3 with
no chat_template in the response, 1 fine-tune match.

These numbers are higher than the HF ones for the same three anchors
(51.4/23.5/22.9 vs 71.4/44.4/68.8) and that's fine -- not expected to
match. Different platform, different publisher community, different
upload timing relative to each anchor's template revisions. What matters
for external validity isn't that the numbers match, it's that the
phenomenon shows up on both: on two independently-sampled registries, a
real chunk of community quantizations diverge from canonical, for all
three verified anchors. The magnitude is registry-specific; that's
informative, not a discrepancy to explain away.

## Unexpected: upstream drift shows up here too

A ModelScope repo published under the `microsoft` name for
Phi-3-mini-4k-instruct carries a template that diverges from current
canonical -- checked, and it's a real content difference (no bos_token,
no system-role handling, simpler structure), not a hashing artifact. Same
mechanism as the Mistral finding: the developer's template moved on, and
this mirror reflects an older revision.

One honest caveat: no way to verify that ModelScope's `microsoft`-labeled
org is actually Microsoft-controlled the way the HF `microsoft/...` repo
was verified as the real canonical source. If it isn't, this case is just
an ordinary third-party divergence, not upstream drift -- either way it
still counts toward the prevalence number, but the upstream-drift
interpretation for this specific case should carry less confidence than
the Mistral finding, which was checked against real upload timestamps.

## What this adds to the paper

A real second data point instead of resting everything on one sampling
frame. The Section 5.1 headline (34.5%, HF-only) doesn't change -- this
is reported separately, not pooled in, same discipline as everywhere
else in this project about not blending different measurements into one
number. Net effect: strengthens the core claim rather than weakening it.
The divergence phenomenon isn't a Hugging-Face-specific artifact.
