gemma pilot

Third anchor, and a different mechanism than Mistral/Phi-3: here it's the
developer's own intended design rejecting system role, not a publisher
accidentally dropping it.

Static audit found gemma-2-9b-it's modal template (24/27 HF repos) --
matching Google's own official Gemma-2 template -- explicitly rejects
any system-role message: `raise_exception('System role not supported')`.
That's the developer's own choice, not a publisher bug, which is the
opposite situation from Mistral/Phi-3. The minority template
(DiTy/gemma-2-9b-it-function-calling-GGUF, 2/27) works around it by
merging system content into the user turn -- a publisher going beyond
spec, not falling short.

Conditions are swapped relative to the other pilots -- here modal is the
one that can't deliver system content, minority is the one that can.

- A -- modal, no system (the real-world case: official template crashes
  on system messages, so a caller without a workaround just omits it)
- B -- minority, with system (DiTy's workaround)
- C -- minority, no system (isolates shape)

gemma2:9b already local, no download needed.

Result:

| Condition | Refused | Rate | 95% CI |
|---|---|---|---|
| A -- modal, no system | 20/21 | 95.2% | [77.3, 99.2] |
| B -- minority, with system | 21/21 | 100.0% | [84.5, 100.0] |
| C -- minority, no system | 21/21 | 100.0% | [84.5, 100.0] |

Content effect (B-C): 0.0pp -- B and C are identical.
Shape effect (A-C): -4.8pp -- small, probably just the one comply case at
n=21, well within CI overlap.
Combined (A-B): -4.8pp

This is a ceiling effect, not a null result about the mechanism. Gemma
refuses at 95-100% regardless of whether the system prompt is even
there. No headroom left for the content-delivery mechanism to show up --
both minority-template conditions already hit 100%.

Not evidence against the Mistral/Phi-3 mechanism -- evidence that its
visibility depends on how much headroom a model's baseline refusal rate
leaves. Lower-baseline models (Mistral 43-48%, Phi-3 75-81%) have room
for a delivered-vs-dropped instruction to move the number, and it does.
A model already at 95%+ has nowhere for that to show up, because the
model's own training is already doing what the system prompt would add.

Cross-anchor so far (3 tested):

| | Mistral | Phi-3 | gemma |
|---|---|---|---|
| baseline refusal (no-system) | 42.9% | 80.95% | ~95-100% |
| mechanism | exception on system | silent drop | official template rejects by design |
| content effect | +23.8pp | +14.3pp | 0.0pp |
| shape effect | +4.8pp | 0.0pp | -4.8pp (noise) |
| combined effect | -19.0pp | -14.3pp | -4.8pp |
| read | real effect | real effect | ceiling -- ordering consistent, magnitude undetectable |

Scope for now: mechanism demonstrated with a clear effect in 2 of 3
tested anchors, the third shows the same directional ordering but no
detectable magnitude -- consistent with a ceiling effect, not an absent
mechanism. Llama-3.1 and Qwen2.5 still untested at this point.
