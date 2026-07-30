"""Recompute divergence prevalence against the CANONICAL upstream template
(fetched from the model developer's own repo), not the modal template among
quantizers -- these are different quantities and the adversarial review
found the paper had been computing the latter while claiming the former.

Canonical templates are fetched from `{repo}/raw/main/tokenizer_config.json`
on the base-model repo itself. Three of five anchors are ungated and
fetchable this way (gold-standard ground truth). Two (Llama-3.1, gemma-2)
are gated on Hugging Face -- genuinely inaccessible without an authenticated
account accepting the license, which this project does not have and will
not attempt to bypass. For those two, this script reports ONLY the modal-
disagreement number (already computed in static_audit_v2.json) and labels
it explicitly as NOT a canonical-deviation measure, rather than substituting
an unverified "trusted quantizer" assumption -- the exact kind of unstated
assumption the adversarial review flagged.

Output: data/results/canonical_divergence_v2.json
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Only anchors with a freely-fetchable (ungated) canonical repo get a true
# canonical-deviation number. Verified 2026-07-28: meta-llama/Meta-Llama-3.1
# -8B-Instruct and google/gemma-2-9b-it both return HTTP 401 on
# tokenizer_config.json without authentication.
CANONICAL_REPOS = {
    "Mistral-7B-Instruct-v0.3": "mistralai/Mistral-7B-Instruct-v0.3",
    "Qwen2.5-7B-Instruct": "Qwen/Qwen2.5-7B-Instruct",
    "Phi-3-mini-4k-instruct": "microsoft/Phi-3-mini-4k-instruct",
}
GATED_ANCHORS = {
    "Llama-3.1-8B-Instruct": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "gemma-2-9b-it": "google/gemma-2-9b-it",
}


def fetch_canonical_template(repo: str) -> tuple[str | None, str | None]:
    """Returns (chat_template, error)."""
    url = f"https://huggingface.co/{repo}/raw/main/tokenizer_config.json"
    try:
        resp = requests.get(url, timeout=20)
    except requests.RequestException as e:
        return None, f"request_error: {e}"
    if resp.status_code != 200:
        return None, f"http_{resp.status_code}"
    data = resp.json()
    ct = data.get("chat_template")
    if isinstance(ct, list):  # some configs declare multiple named templates
        ct = ct[0].get("template") if ct and isinstance(ct[0], dict) else None
    if not isinstance(ct, str):
        return None, "no_chat_template_field"
    return ct, None


def main():
    audit = json.loads((DATA_DIR / "results" / "static_audit_v2.json").read_text())
    results = {}

    for anchor, repo in CANONICAL_REPOS.items():
        ct, err = fetch_canonical_template(repo)
        hashes = audit["summary_by_anchor"][anchor]["hf_repo_hashes"]
        n = len(hashes)
        if err:
            results[anchor] = {"status": "fetch_failed", "error": err, "n_repos": n}
            continue

        canonical_hash = hashlib.sha256(ct.encode()).hexdigest()
        n_diverge_from_canonical = sum(1 for h in hashes.values() if h != canonical_hash)
        modal_hash = Counter(hashes.values()).most_common(1)[0][0]
        modal_matches_canonical = modal_hash == canonical_hash
        n_diverge_from_modal = sum(1 for h in hashes.values() if h != modal_hash)

        results[anchor] = {
            "status": "gold_standard_canonical",
            "canonical_repo": repo,
            "n_repos": n,
            "n_diverge_from_canonical": n_diverge_from_canonical,
            "pct_diverge_from_canonical": round(100 * n_diverge_from_canonical / n, 1),
            "modal_matches_canonical": modal_matches_canonical,
            "n_diverge_from_modal": n_diverge_from_modal,
            "pct_diverge_from_modal": round(100 * n_diverge_from_modal / n, 1),
        }

    for anchor, repo in GATED_ANCHORS.items():
        hashes = audit["summary_by_anchor"][anchor]["hf_repo_hashes"]
        n = len(hashes)
        modal_hash = Counter(hashes.values()).most_common(1)[0][0]
        n_diverge_from_modal = sum(1 for h in hashes.values() if h != modal_hash)
        results[anchor] = {
            "status": "GATED_no_canonical_available",
            "canonical_repo": repo,
            "note": "tokenizer_config.json returns HTTP 401 without an authenticated, "
                    "license-accepting HF account. Not measured. Reporting modal-"
                    "disagreement ONLY -- this is NOT a canonical-deviation number "
                    "and must not be presented as one.",
            "n_repos": n,
            "n_diverge_from_modal": n_diverge_from_modal,
            "pct_diverge_from_modal": round(100 * n_diverge_from_modal / n, 1),
        }

    # Overall canonical-deviation prevalence, computed ONLY over the 3 anchors
    # with gold-standard ground truth -- pooling in the gated anchors' modal
    # numbers would silently convert them into canonical-deviation claims.
    gold = [v for v in results.values() if v["status"] == "gold_standard_canonical"]
    total_repos = sum(v["n_repos"] for v in gold)
    total_diverge = sum(v["n_diverge_from_canonical"] for v in gold)

    out = {
        "canonical_deviation_overall_gold_standard_only": {
            "anchors_included": list(CANONICAL_REPOS.keys()),
            "total_repos": total_repos,
            "total_diverging_from_canonical": total_diverge,
            "pct": round(100 * total_diverge / total_repos, 1) if total_repos else None,
        },
        "by_anchor": results,
    }
    (DATA_DIR / "results" / "canonical_divergence_v2.json").write_text(json.dumps(out, indent=2))

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
