Static audit v2

Corpus: N=148 after the SimPO correction (143 HF repos + 5 official
Ollama entries), scaled to the power-calc target from
scripts/power_calculations.py (N=150-200 for +/-7pp margin at 95% CI).

Two data-quality issues, both caught before anything got reported:

1. Rate limiting. First attempt silently failed on 101 of 150 entries
(HTTP 429, HF rate limit after ~450 prior calls in the same session). Got
a wrong topline of 43.2% from just 44 repos before catching it -- checked
fetch_ok completeness before trusting any number, fixed with
retry-with-backoff (src/hf_gguf.py) and wider spacing, reran clean.
2. Filter contamination. 2 of 150 entries turned out to be SimPO
derivatives that slipped the fine-tune filter. See CORPUS-v2-NOTES.md.
All numbers below are post-correction (N=148/143).

Results:

| Anchor | HF repos OK | Distinct templates | Diverge from modal | Prevalence |
|---|---|---|---|---|
| Llama-3.1-8B-Instruct | 29 | 4 | 13/29 | 44.8% |
| Mistral-7B-Instruct-v0.3 | 35 | 6 | 18/35 | 51.4% |
| Qwen2.5-7B-Instruct | 17 | 2 | 4/17 | 23.5% |
| gemma-2-9b-it | 27 | 4 | 3/27 | 11.1% |
| Phi-3-mini-4k-instruct | 35 | 4 | 8/35 | 22.9% |
| overall | 143 | -- | 46/143 | 32.2% |

Wilson 95% CI on overall prevalence: [25.1, 40.2], margin ~7.5pp, close
enough to the design target.

Popularity breakdown (scripts/stratified_breakdown.py):

| bucket | diverge | prevalence |
|---|---|---|
| high-popularity | 26/75 | 34.7% |
| long-tail | 20/68 | 29.4% |

The going-in hypothesis was that risk concentrates in the long tail.
Doesn't hold -- pooled rates are nearly identical, and per-anchor the
pattern flips direction:

| Anchor | high-pop | long-tail |
|---|---|---|
| Llama-3.1-8B-Instruct | 33.3% | 57.1% (tail worse) |
| Mistral-7B-Instruct-v0.3 | 73.3% | 35.0% (popular worse) |
| Phi-3-mini-4k-instruct | 26.7% | 20.0% |
| Qwen2.5-7B-Instruct | 26.7% | 0.0% (n=2, too small) |
| gemma-2-9b-it | 13.3% | 8.3% |

Mistral stands out -- popular repos there are way more divergent than
long-tail, because (confirmed behaviorally, see the mistral pilot
writeup) the popular quantizers shipped a stale template that predates a
system-role revision the less-popular repos already had. Real finding:
divergence is model-family-idiosyncratic, not popularity-driven. More
interesting than the "long tail is riskier" hypothesis we started with.

Behavioral confirmation on two anchors so far (Mistral, Phi-3) shows the
same mechanism: a template that can't deliver a system-role safety
instruction (Mistral raises an exception, Phi-3 silently drops it)
produces measurably lower refusal on identical weights. Mistral +19.0pp
combined at the original pilot scale, Phi-3 +14.3pp. Same direction, two
different developers/architectures. Full writeup in
experiments/phi3-template-test/STAGE2-PILOT-RESULTS.md.

Worth noting: in the earlier N=40 pilot, gemma and Phi-3 looked
template-consistent (0/7 diverging each). At full scale both show real
divergence (11.1%, 22.9%). Small pilots can produce a false "consistent"
reading just from sample size, not because the population is actually
uniform -- exactly the failure mode the power calc was meant to catch.
Overall prevalence moved from 22.9% (pilot, N=35) to 32.2% (N=143) --
real movement, not noise. Treat N=143 as the number going forward.

Still open: behavioral confirmation for the remaining 3 anchors
(Llama-3.1, Qwen2.5, gemma) to push the generalization claim past 2/5.
Current honest scope is "demonstrated in 2 of 5, same mechanism," not
universal.
