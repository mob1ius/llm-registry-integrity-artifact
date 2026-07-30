# llm-registry-integrity

Code and data for "What's Actually In the Models You Pull?" — a registry-scale audit of chat-template drift in community GGUF quantizations, submitted to USENIX Security '27.

Question: do community-published GGUF chat templates match the template the model developer actually shipped, and if not, does it change model behavior? Short answer: often no, and sometimes yes.

## Layout

```
.
├── data/
│   ├── raw/          corpus construction, exclusion logs
│   └── results/       static audit, canonical diff, upstream drift, hand-val, ModelScope check
├── experiments/       one folder per anchor model, behavioral pilots
├── scripts/           corpus + audit pipeline
├── src/               GGUF header parser, HF API wrapper
├── paper/             USENIX submission build
├── CHECKLIST          maps to USENIX AE checklist items
└── LICENSE
```

## Reproducing

```
pip install -r requirements.txt
python scripts/build_corpus.py --version v2
python scripts/run_static_audit.py
python scripts/canonical_divergence.py
```

Needs a local Ollama instance with the 5 anchor models pulled for the behavioral pilots (`experiments/*/run_pilot*.py`); everything else is static analysis against the HF/ModelScope APIs, no GPU needed.

## Paper

`paper/latex/main.tex` (compiled: `main.pdf`) is the USENIX Security '27 submission.
