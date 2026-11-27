#!/usr/bin/env python3
"""Discover candidate open-source repositories; never clone or execute results."""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timezone
from typing import Any
import requests

API = "https://api.github.com"
ALLOW = {"mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc", "mpl-2.0", "unlicense"}

def search_repositories(query: str, *, session=requests, per_page: int = 30) -> list[dict[str, Any]]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = session.get(f"{API}/search/repositories",
        params={"q": query, "sort": "updated", "order": "desc", "per_page": min(max(per_page, 1), 100)},
        headers=headers, timeout=20)
    response.raise_for_status()
    return response.json().get("items", [])

def score_repository(item: dict[str, Any], *, now: datetime | None = None) -> tuple[int, list[str]]:
    now = now or datetime.now(timezone.utc)
    license_id = str((item.get("license") or {}).get("spdx_id") or "unknown").casefold()
    stars = int(item.get("stargazers_count") or 0)
    pushed = item.get("pushed_at") or item.get("updated_at")
    age_days = 3650
    if pushed:
        try:
            age_days = max(0, (now - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).days)
        except (ValueError, TypeError):
            pass
    score, reasons = 0, []
    if license_id in ALLOW:
        score += 30
        reasons.append(f"permissive-license:{license_id}")
    elif license_id == "unknown":
        reasons.append("license-needs-manual-review")
    else:
        reasons.append(f"non-allowlisted-license:{license_id}")
    if stars >= 10000: score += 20
    elif stars >= 1000: score += 14
    elif stars >= 100: score += 8
    if stars: reasons.append(f"stars:{stars}")
    if age_days <= 30: score += 25; reasons.append("active-within-30d")
    elif age_days <= 180: score += 18; reasons.append("active-within-180d")
    elif age_days <= 365: score += 8; reasons.append("active-within-1y")
    else: reasons.append("stale-or-unknown-activity")
    if item.get("archived"): score -= 35; reasons.append("archived")
    if item.get("disabled"): score -= 50; reasons.append("disabled")
    if item.get("fork"): score -= 3; reasons.append("fork")
    return max(0, min(100, score)), reasons

def discover(queries: list[str], per_query: int = 25) -> list[dict[str, Any]]:
    merged = {}
    for query in queries:
        for item in search_repositories(query, per_page=per_query):
            name = item.get("full_name")
            if not name: continue
            score, reasons = score_repository(item)
            row = {"name": name, "url": item.get("html_url"), "description": item.get("description"),
                "stars": item.get("stargazers_count", 0),
                "license": (item.get("license") or {}).get("spdx_id") or "UNKNOWN",
                "pushed_at": item.get("pushed_at"), "archived": bool(item.get("archived")),
                "score": score, "reasons": reasons, "topics": item.get("topics", [])}
            if name not in merged or row["score"] > merged[name]["score"]: merged[name] = row
        time.sleep(0.15)
    return sorted(merged.values(), key=lambda row: (row["score"], row["stars"]), reverse=True)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--per-query", type=int, default=25)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--output", default="out/repository_scout.json")
    args = parser.parse_args()
    queries = args.queries or [
        "video generation workflow ComfyUI language:Python",
        "AI agent workflow orchestration DAG language:Python",
        "video editing automation FFmpeg language:Python",
        "image video quality assessment open source language:Python",
        "repository discovery GitHub search agent language:Python"]
    try: results = discover(queries, args.per_query)[:max(1, args.limit)]
    except requests.RequestException as error:
        print(f"Repository discovery failed: {error}", file=sys.stderr); return 2
    from pathlib import Path
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "queries": queries,
        "warning": "Scores are triage hints, not security, maintenance or licence approval. Review code, dependencies, model weights and commercial terms.",
        "repositories": results}
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Discovered {len(results)} repositories -> {output}")
    for row in results[:10]:
        print(f'{row["score"]:>3}  {row["name"]}  [{row["license"]}]  {row["url"]}')
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
