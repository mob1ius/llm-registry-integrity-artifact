qwen2.5 -- resolved without running a pilot

Static audit flagged a real hash-level divergence in Qwen2.5-7B-Instruct
GGUFs: bartowski/mradermacher/idasummer/lmstudio-community (2507 chars)
vs Qwen's own repo/MaziyarPanahi/paultimothymooney (2509 chars).

Turned out not to need a pilot. The 2-character diff sits entirely
inside the tool-calling branch (`{% if tools is defined %}...{% endif
%}`) -- a JSON-escaping fix in the example text shown when tool
definitions are present. Rendered both templates with the same
system+user pair, no tool definitions (same setup as every other pilot
here), and got byte-identical output. No possible behavioral difference
to measure for that condition. Running the full 3-condition pilot would
have been a guaranteed null by construction, not by finding anything --
would've burned 15-20 minutes of CPU inference to confirm something
already settled by just rendering the templates.

Worth keeping as a general caveat: hash-based divergence detection can
flag templates that are byte-different but behaviorally identical for a
given prompt shape, since Jinja templates are conditional and two
templates can differ only in a branch a specific test never hits. So the
static audit's raw prevalence number is an upper bound on behaviorally
relevant divergence, not a direct measure of it.

Status: divergence confirmed, no behavioral consequence for the tested
(non-tool-calling) prompt shape. A real, informative null, not a gap in
coverage.
