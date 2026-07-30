"""Build the audit corpus: for each anchor base model, find real GGUF repos
on Hugging Face spanning high-popularity (well-known quantizers) down to
low-popularity (long-tail/individual uploaders), verified to actually exist
and contain >=1 .gguf file before being added to the list.

Also resolves the matching official Ollama library tag, if one exists, via
the Ollama registry manifest endpoint (no model pull).

v1 (N=40) used limit=60 raw candidates and top-3/bottom-4 per anchor -- a
pilot scale, sufficient to validate the method and run the Stage-2 pilot.
v2 targets the power-calculation-justified N=150-200 (see
scripts/power_calculations.py: N=150-200 gives +/-7pp margin on the
observed 22.9% divergence prevalence at 95% CI). Reached by raising the
raw search limit (HF's API accepts limit=200 in one call, confirmed) and
taking deeper per-anchor samples -- NOT by adding new anchor models, since
verifying new canonical_base_model_ids correctly is itself error-prone and
better done deliberately later than rushed now.

Output: data/raw/corpus_{version}.json (version defaults to "v2")
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from hf_gguf import fetch_repo_file_listing  # noqa: E402

HF_SEARCH = "https://huggingface.co/api/models"

# Anchor base models: popular, widely re-quantized, chosen to span
# multiple developers and architectures.
#
# `canonical_base_model_ids`: acceptable values for a candidate repo's
# `cardData.base_model` field for it to count as a genuine re-quantization of
# THIS checkpoint (not a fine-tune/merge/specialized variant, which would
# confound fine-tuning changes with packaging changes -- a different, invalid
# comparison for this study). Includes known aliasing (e.g. "Llama-3.1" vs.
# "Meta-Llama-3.1" naming) seen in the wild. Matching is case-insensitive.
ANCHOR_MODELS = [
    {
        "search": "Llama-3.1-8B-Instruct",
        "ollama_tag": "llama3.1:8b",
        "canonical_base_model_ids": {
            "meta-llama/meta-llama-3.1-8b-instruct",
            "meta-llama/llama-3.1-8b-instruct",
        },
    },
    {
        "search": "Mistral-7B-Instruct-v0.3",
        "ollama_tag": "mistral:7b",
        "canonical_base_model_ids": {"mistralai/mistral-7b-instruct-v0.3"},
    },
    {
        "search": "Qwen2.5-7B-Instruct",
        "ollama_tag": "qwen2.5:7b",
        "canonical_base_model_ids": {"qwen/qwen2.5-7b-instruct"},
    },
    {
        "search": "gemma-2-9b-it",
        "ollama_tag": "gemma2:9b",
        "canonical_base_model_ids": {"google/gemma-2-9b-it"},
    },
    {
        "search": "Phi-3-mini-4k-instruct",
        "ollama_tag": "phi3:3.8b",
        "canonical_base_model_ids": {"microsoft/phi-3-mini-4k-instruct"},
    },
]

REPOS_PER_ANCHOR_HIGH = 15  # top by downloads -- well-known quantizers
REPOS_PER_ANCHOR_LOW = 20  # bottom by downloads (nonzero) -- long tail
SEARCH_RAW_LIMIT = 200  # HF API confirmed to accept this in one call, no pagination needed
MIN_DOWNLOADS_FOR_HIGH = 0  # no floor; we just take the top N

# `cardData.base_model` means "the checkpoint this was built FROM" -- it does
# NOT distinguish an unmodified re-quantization from a legitimate fine-tune /
# preference-tuned / merged derivative that happens to declare the same base
# (e.g. a DPO/RLHF pass, an "abliterated"/uncensored refusal-ablation, a
# roleplay merge). Both use the same field. Since this study's internal
# validity depends on comparing IDENTICAL weights repackaged by different
# publishers -- not different weights that share a lineage -- repo names
# containing these substrings are excluded even if base_model matched.
# Case-insensitive substring match against the repo_id.
FINETUNE_SIGNAL_KEYWORDS = [
    "abliterat", "uncensor", "-dpo", "_dpo", "dpo-", "wpo", "orpo", "kto",
    "ppo", "sft", "-rp-", "roleplay", "sillytavern", "merge", "-ties",
    "-dare", "slerp", "continued-pretrain", "finetune", "fine-tune",
    "-r-2", "-r-1", "instruct-tune", "distill",
    # Added after catching gemma-2-9b-it-SimPO-GGUF slip through the v1/v2
    # filter with a correctly-declared canonical base_model -- same failure
    # mode as the original DPO/WPO catch (the field means "built from X",
    # not "identical to X", and preference-tuning methods legitimately
    # declare their base). Proactively covering other common
    # preference-optimization method names, not just the one instance found.
    "simpo", "cpo", "ipo", "rrhf", "rlaif", "rlhf-tuned", "-grpo", "_grpo",
]


def looks_like_finetune_derivative(repo_id: str) -> str | None:
    """Return the matched keyword if repo_id looks like a fine-tuned /
    preference-tuned / merged derivative rather than a plain re-quantization,
    else None."""
    lower = repo_id.lower()
    for kw in FINETUNE_SIGNAL_KEYWORDS:
        if kw in lower:
            return kw
    return None


def search_gguf_repos(query: str, limit: int = 30) -> list[dict]:
    """Query HF for GGUF-tagged repos matching a search string. Returns raw
    model dicts (id, downloads, etc.) sorted by downloads descending."""
    params = {
        "search": query,
        "filter": "gguf",
        "sort": "downloads",
        "direction": -1,
        "limit": limit,
    }
    resp = requests.get(HF_SEARCH, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_base_model_id(repo_id: str) -> str | None:
    """Return the repo's declared `cardData.base_model` (lowercased), if any."""
    try:
        resp = requests.get(f"{HF_SEARCH}/{repo_id}", params={"expand[]": "cardData"}, timeout=20)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    card = resp.json().get("cardData") or {}
    bm = card.get("base_model")
    if isinstance(bm, list):  # some cards declare a list of base models
        bm = bm[0] if bm else None
    return bm.lower() if isinstance(bm, str) else None


def resolve_ollama_manifest(tag: str) -> dict | None:
    """Fetch the Ollama registry manifest for `library/<name>:<version>` if it
    exists. Returns None if the tag can't be resolved."""
    if ":" in tag:
        name, version = tag.split(":", 1)
    else:
        name, version = tag, "latest"
    url = f"https://registry.ollama.ai/v2/library/{name}/manifests/{version}"
    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    return resp.json()


def build_corpus() -> tuple[list[dict], list[dict]]:
    corpus: list[dict] = []
    excluded: list[dict] = []
    seen_repo_ids: set[str] = set()

    for anchor in ANCHOR_MODELS:
        query = anchor["search"]
        canonical_ids = anchor["canonical_base_model_ids"]
        print(f"=== anchor: {query} (canonical base_model: {sorted(canonical_ids)}) ===", file=sys.stderr)
        try:
            # Over-fetch since many hits will be excluded as non-canonical variants.
            hits = search_gguf_repos(query, limit=SEARCH_RAW_LIMIT)
        except requests.RequestException as e:
            print(f"  search failed: {e}", file=sys.stderr)
            continue

        hits_sorted = sorted(hits, key=lambda h: h.get("downloads", 0), reverse=True)

        # Filter to genuine re-quantizations of the canonical checkpoint FIRST
        # (by declared base_model), then bucket the survivors by popularity.
        # This must happen before bucketing, or "long tail" ends up meaning
        # "long tail of everything" rather than "long tail of valid repos".
        canonical_hits = []
        for item in hits_sorted:
            repo_id = item["id"]
            if repo_id in seen_repo_ids:
                continue
            finetune_kw = looks_like_finetune_derivative(repo_id)
            if finetune_kw:
                excluded.append({
                    "anchor_model": query, "repo_id": repo_id,
                    "declared_base_model": None,
                    "reason": f"finetune_signal_keyword:{finetune_kw}",
                })
                continue

            bm = fetch_base_model_id(repo_id)
            time.sleep(0.15)
            if bm not in canonical_ids:
                excluded.append({
                    "anchor_model": query, "repo_id": repo_id,
                    "declared_base_model": bm, "reason": "base_model_mismatch",
                })
                continue
            canonical_hits.append(item)

        print(f"  {len(canonical_hits)}/{len(hits_sorted)} hits are genuine re-quants "
              f"of the canonical checkpoint", file=sys.stderr)

        high = canonical_hits[:REPOS_PER_ANCHOR_HIGH]
        low_candidates = [h for h in canonical_hits if h.get("downloads", 0) > 0]
        low = sorted(low_candidates, key=lambda h: h.get("downloads", 0))[:REPOS_PER_ANCHOR_LOW]

        for bucket, items in (("high_popularity", high), ("long_tail", low)):
            for item in items:
                repo_id = item["id"]
                if repo_id in seen_repo_ids:
                    continue
                seen_repo_ids.add(repo_id)

                ok, gguf_files, err = fetch_repo_file_listing(repo_id)
                time.sleep(0.2)  # be polite to the API
                if not ok or not gguf_files:
                    print(f"  SKIP {repo_id}: {err or 'no gguf files'}", file=sys.stderr)
                    continue

                entry = {
                    "anchor_model": query,
                    "repo_id": repo_id,
                    "downloads": item.get("downloads", 0),
                    "popularity_bucket": bucket,
                    "n_gguf_files": len(gguf_files),
                    "gguf_filenames_sample": gguf_files[:5],
                }
                corpus.append(entry)
                print(f"  ADD [{bucket}] {repo_id} (downloads={item.get('downloads', 0)}, "
                      f"{len(gguf_files)} gguf files)", file=sys.stderr)

        # Ollama official entry (one per anchor, not a "repo" but tracked
        # alongside for the cross-ecosystem comparison)
        manifest = resolve_ollama_manifest(anchor["ollama_tag"])
        if manifest:
            corpus.append({
                "anchor_model": query,
                "repo_id": f"ollama::{anchor['ollama_tag']}",
                "downloads": None,
                "popularity_bucket": "official_registry",
                "n_gguf_files": None,
                "gguf_filenames_sample": [],
            })
            print(f"  ADD [official_registry] ollama::{anchor['ollama_tag']}", file=sys.stderr)
        else:
            print(f"  SKIP ollama tag {anchor['ollama_tag']}: manifest not found", file=sys.stderr)

    return corpus, excluded


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2", help="output filename version tag")
    args = parser.parse_args()

    corpus, excluded = build_corpus()
    data_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    (data_dir / f"corpus_{args.version}.json").write_text(json.dumps(corpus, indent=2))
    (data_dir / f"corpus_{args.version}_excluded.json").write_text(json.dumps(excluded, indent=2))
    print(f"\nWrote {len(corpus)} entries to corpus_{args.version}.json", file=sys.stderr)
    print(f"Wrote {len(excluded)} excluded (base_model mismatch / finetune-signal) entries to "
          f"corpus_{args.version}_excluded.json", file=sys.stderr)
