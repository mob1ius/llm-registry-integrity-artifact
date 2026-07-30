"""Second, independent-registry corpus to check external validity of the
Hugging Face-based findings (Section 5.1-5.2). Same three anchors with
verified canonical ground truth (Mistral, Qwen2.5, Phi-3), same filtering
discipline (name/base-model match, then fine-tune-keyword exclusion, then
manual spot-check awareness) applied against ModelScope (modelscope.cn)
instead of Hugging Face.

Unlike HF's expand[]=gguf API (single file per repo) or this project's own
GGUF binary-header parser, ModelScope's search API returns the embedded
chat_template string directly in the search response
(ModelInfos.gguf.chat_template) -- no binary parsing required.

Known limitation, stated here rather than hidden: ModelScope's search API
does not expose a reliable declared base_model field the way HF's does, so
model-family filtering here relies on a strict name-prefix match plus an
explicit variant-keyword exclusion list (VL, Coder, 1M-context, etc.),
rather than verified base_model metadata. This is weaker than the primary
HF corpus's two-stage filter and is reported as such in the paper.

Run: python3 scripts/build_modelscope_corpus.py
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MS_API = "https://www.modelscope.cn/api/v1/dolphin/models"

FINETUNE_KEYWORDS = ["dpo", "wpo", "simpo", "cpo", "ipo", "rrhf", "rlaif", "grpo"]

# Model-family variants that share a name prefix with the anchor but are a
# genuinely different model (different training data/capability), not a
# quantization of the anchor itself. Excluded the same way finetune-keyword
# derivatives are excluded from the primary HF corpus.
VARIANT_KEYWORDS = ["vl", "coder", "1m", "abliterated", "math", "vision", "omni", "audio", "embedding"]

ANCHORS = {
    "Mistral-7B-Instruct-v0.3": {
        "search_term": "Mistral-7B-Instruct-v0.3-GGUF",
        "canonical_hf_repo": "mistralai/Mistral-7B-Instruct-v0.3",
    },
    "Qwen2.5-7B-Instruct": {
        "search_term": "Qwen2.5-7B-Instruct-GGUF",
        "canonical_hf_repo": "Qwen/Qwen2.5-7B-Instruct",
    },
    "Phi-3-mini-4k-instruct": {
        "search_term": "Phi-3-mini-4k-instruct-GGUF",
        "canonical_hf_repo": "microsoft/Phi-3-mini-4k-instruct",
    },
}


def looks_like_finetune(name: str, description: str) -> str | None:
    hay = f"{name} {description}".lower()
    for kw in FINETUNE_KEYWORDS:
        if kw in hay:
            return kw
    return None


def looks_like_different_variant(anchor: str, name: str) -> str | None:
    """Return the matched variant keyword if `name` (after stripping the
    anchor prefix) indicates a different model family, not a quantization
    of the anchor itself."""
    name_lower = name.lower()
    anchor_lower = anchor.lower()
    if not name_lower.startswith(anchor_lower):
        return "name_does_not_start_with_anchor"
    remainder = name_lower[len(anchor_lower):]
    for kw in VARIANT_KEYWORDS:
        if kw in remainder:
            return kw
    return None


def search_modelscope(query: str, page_size: int = 100) -> list[dict]:
    resp = requests.put(
        MS_API,
        json={"PageSize": page_size, "PageNumber": 1, "Name": query},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("Data", {}).get("Model", {}).get("Models", []) or []


def main():
    canonical = json.loads((DATA_DIR / "raw" / "canonical_templates_v1.json").read_text())

    corpus = []
    excluded = []

    for anchor, cfg in ANCHORS.items():
        canonical_hash = canonical[anchor]["sha256"]
        seen_ids = set()

        hits = search_modelscope(cfg["search_term"])
        time.sleep(0.3)
        print(f"[{anchor}] query={cfg['search_term']!r}: {len(hits)} raw hits")

        for m in hits:
            name = m.get("Name", "")
            org = (m.get("Organization") or {}).get("Name") or m.get("Path")
            repo_id = f"{org}/{name}"
            if repo_id in seen_ids:
                continue
            seen_ids.add(repo_id)

            libs = m.get("Libraries") or []
            if "gguf" not in [lib.lower() for lib in libs]:
                excluded.append({"anchor": anchor, "repo_id": repo_id, "reason": "not_gguf_library"})
                continue

            variant = looks_like_different_variant(anchor, name)
            if variant:
                excluded.append({"anchor": anchor, "repo_id": repo_id, "reason": f"variant_mismatch:{variant}"})
                continue

            desc = m.get("Description", "") or ""
            kw = looks_like_finetune(name, desc)
            if kw:
                excluded.append({"anchor": anchor, "repo_id": repo_id, "reason": f"finetune_keyword:{kw}"})
                continue

            gguf_info = (m.get("ModelInfos") or {}).get("gguf") or {}
            chat_template = gguf_info.get("chat_template")
            if not chat_template:
                excluded.append({"anchor": anchor, "repo_id": repo_id, "reason": "no_chat_template_in_response"})
                continue

            tmpl_hash = hashlib.sha256(chat_template.encode()).hexdigest()
            corpus.append({
                "anchor": anchor,
                "repo_id": repo_id,
                "downloads": m.get("Downloads", 0),
                "chat_template_sha256": tmpl_hash,
                "diverges_from_canonical": tmpl_hash != canonical_hash,
            })

    Path(DATA_DIR / "results").mkdir(exist_ok=True)
    out = {
        "source": "modelscope.cn",
        "purpose": "external-validity check against the primary Hugging Face corpus (Section 5.1-5.2)",
        "corpus": corpus,
        "excluded": excluded,
    }
    (DATA_DIR / "results" / "modelscope_corpus_v1.json").write_text(json.dumps(out, indent=2))
    print(f"\nTotal included: {len(corpus)}, excluded: {len(excluded)}")

    by_anchor = {}
    for anchor in ANCHORS:
        rows = [r for r in corpus if r["anchor"] == anchor]
        n = len(rows)
        div = sum(1 for r in rows if r["diverges_from_canonical"])
        by_anchor[anchor] = {"n": n, "diverge": div, "pct": round(100 * div / n, 1) if n else None}
        print(anchor, by_anchor[anchor])

    (DATA_DIR / "results" / "modelscope_summary_v1.json").write_text(json.dumps(by_anchor, indent=2))


if __name__ == "__main__":
    main()
