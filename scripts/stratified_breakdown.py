"""Popularity-stratified divergence breakdown on the static audit results.

Joins corpus_{version}.json (which has popularity_bucket) with
static_audit_{version}.json (which has the per-repo template hashes) to
report divergence-from-modal prevalence split by high_popularity vs.
long_tail, both pooled and per-anchor.

Run: python3 scripts/stratified_breakdown.py --version v2
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def main(version: str):
    corpus = json.loads((DATA_DIR / "raw" / f"corpus_{version}.json").read_text())
    audit = json.loads((DATA_DIR / "results" / f"static_audit_{version}.json").read_text())
    bucket_by_repo = {e["repo_id"]: e["popularity_bucket"] for e in corpus}

    rows = []
    for anchor, s in audit["summary_by_anchor"].items():
        hashes = s["hf_repo_hashes"]
        if not hashes:
            continue
        modal_hash = Counter(hashes.values()).most_common(1)[0][0]
        for repo, h in hashes.items():
            rows.append({
                "anchor": anchor, "repo": repo,
                "bucket": bucket_by_repo.get(repo, "UNKNOWN"),
                "diverges": h != modal_hash,
            })

    unknown = [r for r in rows if r["bucket"] == "UNKNOWN"]
    if unknown:
        print(f"WARNING: {len(unknown)} repos with unresolved popularity bucket:",
              [r["repo"] for r in unknown])

    by_bucket = defaultdict(lambda: {"n": 0, "div": 0})
    for r in rows:
        by_bucket[r["bucket"]]["n"] += 1
        by_bucket[r["bucket"]]["div"] += r["diverges"]

    by_anchor_bucket = defaultdict(lambda: {"n": 0, "div": 0})
    for r in rows:
        key = (r["anchor"], r["bucket"])
        by_anchor_bucket[key]["n"] += 1
        by_anchor_bucket[key]["div"] += r["diverges"]

    result = {
        "total_repos_analyzed": len(rows),
        "by_bucket": {
            b: {"n": d["n"], "diverging": d["div"], "pct": round(100 * d["div"] / d["n"], 1)}
            for b, d in by_bucket.items()
        },
        "by_anchor_and_bucket": {
            f"{a} / {b}": {"n": d["n"], "diverging": d["div"], "pct": round(100 * d["div"] / d["n"], 1) if d["n"] else None}
            for (a, b), d in sorted(by_anchor_bucket.items())
        },
    }

    out_path = DATA_DIR / "results" / f"stratified_breakdown_{version}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(f"total repos analyzed: {len(rows)}\n")
    print("=== overall by popularity bucket ===")
    for b, d in result["by_bucket"].items():
        print(f"  {b}: {d['diverging']}/{d['n']} = {d['pct']}%")
    print("\n=== per-anchor x bucket ===")
    for k, d in result["by_anchor_and_bucket"].items():
        print(f"  {k}: {d['diverging']}/{d['n']} = {d['pct']}%")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2")
    args = parser.parse_args()
    main(args.version)
