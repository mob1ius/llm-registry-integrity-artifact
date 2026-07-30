"""Operationalize the 4th threat category from Chapter Plan Ch.2 (upstream
checkpoint/template drift, non-adversarial): for repos that diverge from
their anchor's canonical/modal template, check whether they were uploaded
BEFORE a plausible upstream template revision -- consistent with staleness,
not publisher negligence -- versus AFTER, which is harder to explain as
drift alone.

Caveat, stated in the output: repo-level `lastModified` reflects the last
change to ANY file in the repo, not specifically the chat_template's own
revision history. `createdAt` (when the repo was first pushed) is the more
reliable signal for "was this quantization done before or after a known
template change" and is what this script primarily uses.

Output: data/results/upstream_drift_v2.json
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HF_API_BASE = "https://huggingface.co/api/models"


def fetch_timestamps(repo: str) -> dict:
    try:
        resp = requests.get(f"{HF_API_BASE}/{repo}", timeout=20)
    except requests.RequestException as e:
        return {"ok": False, "error": str(e)}
    if resp.status_code != 200:
        return {"ok": False, "error": f"http_{resp.status_code}"}
    data = resp.json()
    return {"ok": True, "createdAt": data.get("createdAt"), "lastModified": data.get("lastModified")}


def main():
    audit = json.loads((DATA_DIR / "results" / "static_audit_v2.json").read_text())
    canon = json.loads((DATA_DIR / "results" / "canonical_divergence_v2.json").read_text())

    results = {}
    for anchor, summary in audit["summary_by_anchor"].items():
        hashes = summary["hf_repo_hashes"]
        if not hashes:
            continue
        modal_hash = Counter(hashes.values()).most_common(1)[0][0]

        anchor_repos = []
        for i, (repo, h) in enumerate(hashes.items()):
            print(f"[{anchor}] [{i + 1}/{len(hashes)}] {repo}", file=sys.stderr)
            ts = fetch_timestamps(repo)
            time.sleep(0.3)
            anchor_repos.append({
                "repo": repo,
                "diverges_from_modal": h != modal_hash,
                **ts,
            })
        results[anchor] = anchor_repos

    # For each anchor, find the earliest createdAt among the NON-divergent
    # (modal/canonical) repos, as a rough proxy for "when the current
    # template became the norm" -- then check what fraction of DIVERGENT
    # repos were created before vs after that point.
    summary_out = {}
    for anchor, repos in results.items():
        ok_repos = [r for r in repos if r.get("ok") and r.get("createdAt")]
        modal_repos = [r for r in ok_repos if not r["diverges_from_modal"]]
        divergent_repos = [r for r in ok_repos if r["diverges_from_modal"]]
        if not modal_repos or not divergent_repos:
            summary_out[anchor] = {"note": "insufficient data (need both modal and divergent repos with timestamps)"}
            continue
        earliest_modal = min(r["createdAt"] for r in modal_repos)
        n_divergent_before = sum(1 for r in divergent_repos if r["createdAt"] < earliest_modal)
        n_divergent_after = len(divergent_repos) - n_divergent_before
        summary_out[anchor] = {
            "n_modal_repos_with_timestamp": len(modal_repos),
            "n_divergent_repos_with_timestamp": len(divergent_repos),
            "earliest_modal_repo_createdAt": earliest_modal,
            "divergent_repos_created_before_earliest_modal": n_divergent_before,
            "divergent_repos_created_after_earliest_modal": n_divergent_after,
            "pct_divergent_explainable_by_staleness": round(
                100 * n_divergent_before / len(divergent_repos), 1
            ) if divergent_repos else None,
        }

    out = {
        "caveat": "Repo-level createdAt/lastModified reflect the whole repo, not "
                  "the chat_template file's own revision history specifically. "
                  "This is a proxy analysis, not a precise file-level drift audit.",
        "summary_by_anchor": summary_out,
        "raw_timestamps": results,
    }
    (DATA_DIR / "results" / "upstream_drift_v2.json").write_text(json.dumps(out, indent=2))
    print("\n=== SUMMARY ===", file=sys.stderr)
    print(json.dumps(summary_out, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
