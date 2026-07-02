from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import requests

from behavior_reader.crawler import USER_AGENT
from behavior_reader.research import (
    candidate_is_robotics,
    extract_site_metadata,
    extract_challenge_page_title,
    normalize_name,
    parse_contributors,
)


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
HOMEPAGE = "https://behavior.stanford.edu/"
CHALLENGE_PAGE = "https://behavior.stanford.edu/challenge/"
OPENALEX = "https://api.openalex.org"
CROSSREF = "https://api.crossref.org"


def get_json(session: requests.Session, url: str, params: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(5):
        response = session.get(url, params=params, timeout=30)
        if response.status_code not in {429, 500, 502, 503, 504}:
            response.raise_for_status()
            return response.json()
        time.sleep(2**attempt)
    response.raise_for_status()
    return {}


def discover_openalex(
    session: requests.Session,
    contributors: list[dict[str, str]],
    delay: float,
    candidate_path: Path,
    progress_path: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = (
        json.loads(candidate_path.read_text(encoding="utf-8"))
        if candidate_path.exists()
        else []
    )
    completed: set[str] = (
        set(json.loads(progress_path.read_text(encoding="utf-8")))
        if progress_path.exists()
        else set()
    )
    for contributor in contributors:
        if contributor["name"] in completed:
            continue
        try:
            author_data = get_json(
                session,
                f"{OPENALEX}/authors",
                {"search": contributor["name"], "per-page": 5},
            )
        except requests.RequestException as exc:
            print(f"Skipped author lookup for {contributor['name']}: {exc}")
            continue
        candidates = author_data.get("results", [])
        if not candidates:
            completed.add(contributor["name"])
            progress_path.write_text(
                json.dumps(sorted(completed), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            continue
        author = max(
            candidates,
            key=lambda item: (
                "stanford" in str(item.get("last_known_institutions", "")).casefold(),
                item.get("works_count", 0),
            ),
        )
        try:
            works_data = get_json(
                session,
                f"{OPENALEX}/works",
                {
                    "filter": f"author.id:{author['id']},from_publication_date:2022-01-01,to_publication_date:2026-07-01",
                    "per-page": 200,
                    "select": "id,doi,title,publication_year,primary_location,topics",
                },
            )
        except requests.RequestException as exc:
            print(f"Skipped works lookup for {contributor['name']}: {exc}")
            continue
        for work in works_data.get("results", []):
            compact = {
                "person": contributor["name"],
                "contributor_group": contributor["group"],
                "homepage": contributor["homepage"],
                "openalex_author_id": author["id"],
                "paper": work.get("title", ""),
                "year": work.get("publication_year", ""),
                "doi": work.get("doi", "") or "",
                "paper_url": (
                    (work.get("primary_location") or {}).get("landing_page_url")
                    or work.get("id", "")
                ),
                "topics": [
                    topic.get("display_name", "") for topic in work.get("topics", [])
                ],
            }
            if candidate_is_robotics(compact):
                rows.append(compact)
        completed.add(contributor["name"])
        candidate_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        progress_path.write_text(
            json.dumps(sorted(completed), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[{len(completed)}/{len(contributors)}] {contributor['name']}")
        time.sleep(delay)
    return rows


def discover_crossref(
    session: requests.Session,
    contributors: list[dict[str, str]],
    delay: float,
    candidate_path: Path,
    progress_path: Path,
) -> list[dict[str, Any]]:
    rows = (
        json.loads(candidate_path.read_text(encoding="utf-8"))
        if candidate_path.exists()
        else []
    )
    roster_version = hashlib.sha256(
        json.dumps(
            [(row["name"], row["group"]) for row in contributors],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    progress_data = (
        json.loads(progress_path.read_text(encoding="utf-8"))
        if progress_path.exists()
        else {}
    )
    if isinstance(progress_data, list) or progress_data.get("roster_version") != roster_version:
        completed: set[str] = set()
    else:
        completed = set(progress_data.get("completed", []))
    for contributor in contributors:
        if contributor["name"] in completed:
            continue
        try:
            data = get_json(
                session,
                f"{CROSSREF}/works",
                {
                    "query.author": contributor["name"],
                    "query": "robot robotics manipulation embodied teleoperation",
                    "filter": "from-pub-date:2022-01-01,until-pub-date:2026-07-01",
                    "rows": 50,
                    "select": "DOI,title,author,published,URL,subject",
                },
            )
        except requests.RequestException as exc:
            print(f"Skipped Crossref lookup for {contributor['name']}: {exc}")
            continue
        target = normalize_name(contributor["name"])
        for work in data.get("message", {}).get("items", []):
            author_names = [
                normalize_name(
                    " ".join(
                        part
                        for part in [author.get("given", ""), author.get("family", "")]
                        if part
                    )
                )
                for author in work.get("author", [])
            ]
            if target not in author_names:
                continue
            date_parts = work.get("published", {}).get("date-parts", [[]])
            year = date_parts[0][0] if date_parts and date_parts[0] else ""
            compact = {
                "person": contributor["name"],
                "contributor_group": contributor["group"],
                "homepage": contributor["homepage"],
                "paper": (work.get("title") or [""])[0],
                "year": year,
                "doi": work.get("DOI", ""),
                "paper_url": work.get("URL", ""),
                "topics": work.get("subject", []),
                "discovery_source": "Crossref",
            }
            if candidate_is_robotics(compact):
                rows.append(compact)
        completed.add(contributor["name"])
        candidate_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        progress_path.write_text(
            json.dumps(
                {"roster_version": roster_version, "completed": sorted(completed)},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[{len(completed)}/{len(contributors)}] {contributor['name']}")
        time.sleep(delay)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--discover-openalex", action="store_true")
    parser.add_argument("--discover-crossref", action="store_true")
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    response = session.get(HOMEPAGE, timeout=30)
    response.raise_for_status()
    (RAW / "homepage.html").write_text(response.text, encoding="utf-8")
    challenge_response = session.get(CHALLENGE_PAGE, timeout=30)
    challenge_response.raise_for_status()
    (RAW / "challenge.html").write_text(challenge_response.text, encoding="utf-8")
    contributors = parse_contributors(response.text, HOMEPAGE)
    site_metadata = extract_site_metadata(response.text)
    challenge_landing_name = extract_challenge_page_title(challenge_response.text)
    fetched_at = datetime.now(timezone.utc).isoformat()
    (ROOT / "data" / "contributors.json").write_text(
        json.dumps(contributors, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (ROOT / "data" / "site_snapshot.json").write_text(
        json.dumps(
            {
                "source_url": HOMEPAGE,
                "fetched_at": fetched_at,
                "challenge_name": site_metadata["challenge_name"],
                "challenge_landing_name": challenge_landing_name,
                "contributor_count": len(contributors),
                "group_counts": {
                    group: sum(row["group"] == group for row in contributors)
                    for group in ("Core Team", "Supporting Team", "Alumni")
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Collected {len(contributors)} official contributors")

    if args.discover_openalex:
        candidate_path = ROOT / "data" / "openalex_candidates.json"
        progress_path = RAW / "openalex_progress.json"
        candidates = discover_openalex(
            session,
            contributors,
            args.delay,
            candidate_path,
            progress_path,
        )
        candidate_path.write_text(
            json.dumps(candidates, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Discovered {len(candidates)} robotics paper candidates")
    if args.discover_crossref:
        candidate_path = ROOT / "data" / "crossref_candidates.json"
        progress_path = RAW / "crossref_progress.json"
        candidates = discover_crossref(
            session,
            contributors,
            args.delay,
            candidate_path,
            progress_path,
        )
        candidate_path.write_text(
            json.dumps(candidates, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Discovered {len(candidates)} Crossref robotics paper candidates")


if __name__ == "__main__":
    main()
