"""Run the static metadata audit across data/raw/corpus_v1.json.

For each HF repo entry: fetch repo-level GGUF metadata (chat_template, bos/eos)
via the HF expand API. For each Ollama entry: fetch the registry manifest,
locate the template/params blobs, and fetch their content directly.

Groups results by anchor_model and flags any chat_template divergence within
the group (the core static-audit question: do publishers of "the same" model
ship different templates?).

Output: data/results/static_audit_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from hf_gguf import fetch_gguf_metadata  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch_ollama_template_and_params(tag: str) -> dict:
    """Fetch the actual template/params blob content (not just the manifest)
    for an Ollama library tag."""
    name, version = (tag.split(":", 1) + ["latest"])[:2] if ":" in tag else (tag, "latest")
    manifest_url = f"https://registry.ollama.ai/v2/library/{name}/manifests/{version}"
    try:
        resp = requests.get(manifest_url, timeout=15)
    except requests.RequestException as e:
        return {"ok": False, "error": f"manifest_error: {e}"}
    if resp.status_code != 200:
        return {"ok": False, "error": f"manifest_http_{resp.status_code}"}
    manifest = resp.json()

    layers = {layer["mediaType"].split(".")[-1]: layer["digest"] for layer in manifest.get("layers", [])}
    out = {"ok": True, "template": None, "params": None}
    for kind in ("template", "params"):
        digest = layers.get(kind)
        if not digest:
            continue
        blob_url = f"https://registry.ollama.ai/v2/library/{name}/blobs/{digest}"
        try:
            blob_resp = requests.get(blob_url, timeout=20, allow_redirects=True)
            if blob_resp.status_code == 200:
                out[kind] = blob_resp.text
        except requests.RequestException:
            pass
    return out


def audit_entry(entry: dict) -> dict:
    repo_id = entry["repo_id"]
    if repo_id.startswith("ollama::"):
        tag = repo_id.split("::", 1)[1]
        result = fetch_ollama_template_and_params(tag)
        template = result.get("template")
        return {
            **entry,
            "source": "ollama_registry",
            "chat_template": template,
            "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest() if template else None,
            "chat_template_len": len(template) if template else 0,
            "params": result.get("params"),
            "fetch_ok": result.get("ok", False),
            "fetch_error": result.get("error"),
        }
    else:
        rec = fetch_gguf_metadata(repo_id)
        return {
            **entry,
            "source": "hf_repo_level",
            "chat_template": rec.chat_template,
            "chat_template_sha256": rec.chat_template_sha256,
            "chat_template_len": rec.chat_template_len,
            "bos_token": rec.bos_token,
            "eos_token": rec.eos_token,
            "fetch_ok": rec.ok,
            "fetch_error": rec.error,
        }


def main(version: str):
    corpus = json.loads((DATA_DIR / "raw" / f"corpus_{version}.json").read_text())
    results = []
    for i, entry in enumerate(corpus):
        print(f"[{i + 1}/{len(corpus)}] {entry['repo_id']}", file=sys.stderr)
        results.append(audit_entry(entry))
        time.sleep(0.6)  # widened after observing HTTP 429s at 0.2s spacing on a 150-entry run

    # Group by anchor model, flag divergence (excluding Ollama entries from the
    # HF-vs-HF hash comparison, since they use a different templating language
    # -- flagged separately as a distinct comparison per the method plan).
    by_anchor: dict[str, list[dict]] = {}
    for r in results:
        by_anchor.setdefault(r["anchor_model"], []).append(r)

    summary = {}
    total_hf_repos = 0
    total_divergent_repos = 0
    for anchor, entries in by_anchor.items():
        hf_entries = [e for e in entries if e["source"] == "hf_repo_level" and e.get("fetch_ok")]
        ollama_entries = [e for e in entries if e["source"] == "ollama_registry" and e.get("fetch_ok")]
        hashes = {e["repo_id"]: e["chat_template_sha256"] for e in hf_entries if e["chat_template_sha256"]}
        distinct_hashes = set(hashes.values())

        # Prevalence: how many repos diverge from their anchor's MODAL (most
        # common) template, not just "are there >1 distinct hashes" -- this is
        # the number the corpus-size power calculation is actually about.
        n_divergent = 0
        if len(distinct_hashes) > 1:
            modal_hash, _ = Counter(hashes.values()).most_common(1)[0]
            n_divergent = sum(1 for h in hashes.values() if h != modal_hash)
        total_hf_repos += len(hashes)
        total_divergent_repos += n_divergent

        summary[anchor] = {
            "n_hf_entries_ok": len(hf_entries),
            "n_hf_distinct_templates": len(distinct_hashes),
            "hf_divergence_detected": len(distinct_hashes) > 1,
            "n_divergent_from_modal": n_divergent,
            "divergence_prevalence_pct": round(100 * n_divergent / len(hashes), 1) if hashes else None,
            "n_ollama_entries_ok": len(ollama_entries),
            "hf_repo_hashes": hashes,
        }

    overall_prevalence = round(100 * total_divergent_repos / total_hf_repos, 1) if total_hf_repos else None

    out = {
        "corpus_version": version,
        "overall": {
            "total_hf_repos": total_hf_repos,
            "total_divergent_from_modal": total_divergent_repos,
            "overall_divergence_prevalence_pct": overall_prevalence,
        },
        "entries": results,
        "summary_by_anchor": summary,
    }
    (DATA_DIR / "results" / f"static_audit_{version}.json").write_text(json.dumps(out, indent=2))

    print("\n=== SUMMARY ===", file=sys.stderr)
    for anchor, s in summary.items():
        flag = "DIVERGENCE" if s["hf_divergence_detected"] else "consistent"
        print(f"{anchor}: {s['n_hf_entries_ok']} HF repos OK, "
              f"{s['n_hf_distinct_templates']} distinct templates -> {flag} "
              f"({s['n_divergent_from_modal']}/{s['n_hf_entries_ok']} = {s['divergence_prevalence_pct']}% diverge from modal) "
              f"| {s['n_ollama_entries_ok']} Ollama entries OK", file=sys.stderr)
    print(f"\nOVERALL: {total_divergent_repos}/{total_hf_repos} repos diverge from their anchor's modal "
          f"template = {overall_prevalence}%", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2")
    args = parser.parse_args()
    main(args.version)
