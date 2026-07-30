llama-3.1 pilot

Fourth anchor tested, rounding out the anchors with a real static-audit
flagged divergence (Qwen2.5's got resolved analytically instead --
see experiments/qwen25-template-test/STAGE2-PILOT-RESULTS.md). Pulled
llama3.1:8b specifically for this (4.9GB, approved beforehand) since it
had to be the exact weights the flagged divergence applies to, no
substitute would do.

Different case again, not forced into the same shape as the others.
Unlike Mistral/Phi-3 (content unreachable) or gemma (developer-mandated
rejection), both Llama-3.1 templates actually deliver a system message --
verified by direct rendering. The modal template (MaziyarPanahi et al,
16/27 repos) is a plain role-header loop, no tool-calling scaffolding.
The minority template (bartowski et al, 11/27) is the full tool-calling
version -- system-message extraction, date injection, "Environment:
ipython" boilerplate. So the actual question here is different: does
template verbosity alone shift refusal, holding content constant and
delivered in both arms?

- A -- modal, with system (what most users actually get)
- B -- minority, with system (verbose tool-calling rendering of the same
  content)
- C -- modal, no system (baseline)

Result:

| Condition | Refused | Rate | 95% CI |
|---|---|---|---|
| A -- modal, with system | 20/21 | 95.2% | [77.3, 99.2] |
| B -- minority, with system | 18/21 | 85.7% | [65.4, 95.0] |
| C -- modal, no system | 20/21 | 95.2% | [77.3, 99.2] |

Content-delivery effect within modal (A-C): 0.0pp -- A and C identical.
Like gemma, this anchor already refuses at ~95% regardless of whether
system prompt is present -- a third ceiling case for the content-delivery
mechanism.

Pure shape effect (A-B): +9.5pp. This is new -- even holding content
constant and delivered in both arms, the simpler template gets more
refusals than the verbose tool-calling one. CIs overlap at n=21
([77.3,99.2] vs [65.4,95.0]), not confirmed yet, but it's the cleanest
isolated read on "does verbosity alone matter" across all the pilots --
the other three all conflated shape with content-presence to some degree.

Doesn't replicate the "instruction gets dropped" story -- can't, since
both templates deliver it here. What it adds instead: a hint that
template verbosity itself, independent of content, might nudge refusal
behavior a little, maybe because the tool-calling boilerplate
("Environment: ipython", "Tools:") shifts the model toward a more
permissive task-execution register even with no tools actually invoked.
Speculative, needs a properly-powered follow-up (~86-195 prompts per
condition per the power calc), but it's a genuine, novel, honestly-
reported result, not a forced fit to the other anchors' mechanism.

## Where things stand across all 5 anchors

| Anchor | Baseline (no-system) | Mechanism | Content effect | Shape effect | Status |
|---|---|---|---|---|---|
| Mistral-7B-v0.3 | 42.9% | exception on system | +23.8pp | +4.8pp (noise) | real effect |
| Phi-3-mini-4k-instruct | 80.95% | silent drop | +14.3pp | 0.0pp | real effect |
| gemma-2-9b-it | ~95-100% | official template rejects by design | 0.0pp | -4.8pp (noise) | ceiling |
| Llama-3.1-8B-Instruct | ~95% | both deliver, differ in verbosity | 0.0pp | +9.5pp (overlap) | ceiling; novel shape finding |
| Qwen2.5-7B-Instruct | not tested | unexercised code path | N/A | N/A | resolved analytically |

Content-delivery effect shows up clearly in the two lower-baseline
anchors, ceilings out in the two higher-baseline ones, and Qwen2.5's
flagged divergence just doesn't matter for ordinary use. Behavioral
testing was attempted across all five; the honest tally is one confirmed
effect (Mistral, at n=56), one real-but-underpowered effect (Phi-3), two
ceiling effects, and one non-issue -- not five equally-weighted findings.
