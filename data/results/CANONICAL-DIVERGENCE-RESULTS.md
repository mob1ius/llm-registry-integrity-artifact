# Canonical divergence, corrected

A review pass on the draft caught a real gap: `scripts/run_static_audit.py`
computes divergence from the *modal* template among quantizers, but the
writeup was claiming divergence from the *canonical* template the
developer actually shipped. Those aren't the same thing, and if the
popular template happened to be the broken one, we'd have had the sign
backwards -- counting the correct template as the outlier. This resolves
it with real data instead of an assumption.

## What's actually verified

Fetched `chat_template` directly from `{repo}/raw/main/tokenizer_config.json`
on each developer's own repo. 3 of 5 are ungated and fetchable:

| Anchor | Canonical repo | Access |
|---|---|---|
| Mistral-7B-Instruct-v0.3 | mistralai/Mistral-7B-Instruct-v0.3 | 200, fetched |
| Qwen2.5-7B-Instruct | Qwen/Qwen2.5-7B-Instruct | 200, fetched |
| Phi-3-mini-4k-instruct | microsoft/Phi-3-mini-4k-instruct | 200, fetched |
| Llama-3.1-8B-Instruct | meta-llama/Meta-Llama-3.1-8B-Instruct | 401, gated |
| gemma-2-9b-it | google/gemma-2-9b-it | 401, gated |

The two gated ones need an authenticated HF account that's accepted the
license, which we don't have and aren't getting just to bypass a gate. No
proxy either -- was tempted to just treat bartowski's copy as ground
truth for these, but bartowski's README doesn't claim fidelity to
canonical, so that would just move the same unverified assumption
somewhere else, not fix it. For these two, only modal-disagreement gets
reported, and it's labeled as exactly that, not a canonical-deviation
number.

## Result

| Anchor | N | Diverge from canonical | % | Modal = canonical? |
|---|---|---|---|---|
| Mistral-7B-Instruct-v0.3 | 35 | 18 | 51.4% | yes |
| Qwen2.5-7B-Instruct | 17 | 4 | 23.5% | yes |
| Phi-3-mini-4k-instruct | 35 | 8 | 22.9% | yes |
| pooled (3 verified) | 87 | 30 | 34.5% | -- |

For all three where we have ground truth, modal turned out to equal
canonical. Numbers don't change from the earlier modal-based figures --
but now they're checked, not assumed.

| Anchor | Modal-disagreement % (not canonical-verified) |
|---|---|
| Llama-3.1-8B-Instruct | 44.8% |
| gemma-2-9b-it | 11.1% |

## The check that actually mattered

If the pilot's "system-delivered" arm had turned out to be the divergent
template and "no-system" the canonical one, the whole causal story runs
backwards. Checked directly against the verified hashes, for both anchors
with a real behavioral effect:

| Anchor | "system-delivered" arm | "no-system" arm |
|---|---|---|
| Mistral-7B-v0.3 | e16746b4... -- matches canonical | 26a59556... -- diverges (used by MaziyarPanahi/lmstudio-community/SanctumAI) |
| Phi-3-mini-4k-instruct | dcaee66d... -- matches canonical | 268b6082... -- diverges |

No inversion. The template that delivers the safety system prompt is the
one the developer shipped; the one that fails to is a publisher-side
divergence. That's the direction the paper needs, and now it's verified
rather than assumed.

## Numbers for the paper

- Headline: 34.5% (30/87) diverge from canonical, across Mistral/Qwen2.5/Phi-3.
- Separate, secondary: modal-disagreement 44.8% (Llama-3.1) and 11.1%
  (gemma), not pooled into the headline.
- Don't report a blended "32.2% across all 5" as a canonical-deviation
  number -- that's exactly the mistake caught above, treating 2 unverified
  anchors as if confirmed.
- The two behaviorally-confirmed effects (Mistral, Phi-3) are now
  double-grounded: real verified static divergence plus a real behavioral
  effect, causal direction checked, not assumed.

## Still open

Canonical grounding is missing for 2/5 anchors because of HF's gating,
which is a structural limit of studying gated families, not a choice we
made. And even where canonical is available, this only checks the
template itself -- didn't cross-check sampling params or default system
prompt in canonical configs the same way. Worth doing if there's time
before the writeup is final.
