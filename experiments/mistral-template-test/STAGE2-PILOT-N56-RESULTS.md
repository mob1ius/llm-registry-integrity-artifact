mistral, scaled to n=56

Every pilot ran at n=21, below the power-calc targets (n=53-195
depending on effect size) -- meaning nothing was statistically
significant yet. n=56 clears the n=53 target for the ~19-24pp effect
this pilot's own n=21 data suggested, at 80% power. Generated the 35 new
prompts not already run (topup_to_n56.py) and merged with the original
21. No wasted compute.

| Condition | n=21 | n=56 | 95% CI (n=56) |
|---|---|---|---|
| A -- popular template, no system | 47.6% | 46.4% (26/56) | [34.0, 59.3] |
| B -- canonical template, with system | 66.7% | 73.2% (41/56) | [60.4, 83.0] |
| C -- canonical template, no system | 42.9% | 37.5% (21/56) | [26.0, 50.6] |

Content effect (B-C): +35.7pp (was +23.8pp at n=21 -- grew, not shrank)
Shape effect (A-C): +8.9pp (was +4.8pp)
Combined (A-B): -26.8pp (was -19.0pp)

B vs C is now statistically significant: [60.4, 83.0] vs [26.0, 50.6]
don't overlap. First significant behavioral result in this project. At
n=21 this was a real point estimate that couldn't clear the noise floor;
at n=56 it does.

A vs C (shape) still overlaps ([34.0, 59.3] vs [26.0, 50.6]) -- expected,
the shape effect is smaller (~9pp) and per the power table needs n~195 to
resolve. n=56 was never going to get there and wasn't trying to. A vs B
(combined) is close to non-overlapping, ~1pp gap between bounds --
basically what you'd expect from blending a confirmed component with an
unconfirmed one.

Worth flagging: the point estimate grew with more data (19.0->26.8
combined, 23.8->35.7 content), not shrank. Real update, not
cherry-picking -- all 35 new prompts ran and got included, nothing
excluded. Just a reminder that n=21 was noisy even though it pointed the
right direction; n=56 is the better number.
