from __future__ import annotations

from collections import defaultdict
import re
import unicodedata
from typing import Any, Iterable

import pandas as pd
from bs4 import BeautifulSoup, Tag


YEAR_MIN = 2022
YEAR_MAX = 2026

MODEL_ALIASES = {
    "panda": "Franka Emika Panda",
    "franka panda": "Franka Emika Panda",
    "franka emika panda": "Franka Emika Panda",
    "fr3": "Franka Research 3",
    "franka research 3": "Franka Research 3",
    "galaxea r1": "Galaxea R1",
    "r1": "Galaxea R1",
    "r1 pro": "Galaxea R1 Pro",
    "r1pro": "Galaxea R1 Pro",
    "tiago": "PAL Robotics TIAGo (dual-arm configuration)",
    "tiago++": "PAL Robotics TIAGo (dual-arm configuration)",
    "pal robotics tiago++": "PAL Robotics TIAGo (dual-arm configuration)",
    "pal robotics tiago (dual-arm configuration)": "PAL Robotics TIAGo (dual-arm configuration)",
    "vx300s": "Trossen ViperX 300",
    "viperx 300": "Trossen ViperX 300",
    "widowx 250": "Trossen WidowX 250",
    "widowx 250s": "Trossen WidowX 250",
    "stretch": "Hello Robot Stretch",
    "stretch 2": "Hello Robot Stretch 2",
    "fetch": "Fetch",
    "two integrated r1 arms": "Galaxea R1 integrated arm (6-DoF)",
    "two integrated 6-dof r1 arms": "Galaxea R1 integrated arm (6-DoF)",
    "two integrated tiago arms": "PAL Robotics TIAGo integrated arm (7-DoF)",
}

PERSON_ALIASES = {"tianyuan dai": "roger dai"}


def normalize_name(value: str) -> str:
    value = re.sub(r"\([^)]*\)", " ", value)
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_name = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9]+", " ", ascii_name.casefold()).strip()
    return PERSON_ALIASES.get(normalized, normalized)


def extract_site_metadata(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    challenge = ""
    for anchor in soup.find_all("a"):
        text = anchor.get_text(" ", strip=True)
        if re.search(r"\b20\d{2}\s+BEHAVIOR Challenge\b", text):
            challenge = re.search(r"20\d{2}\s+BEHAVIOR Challenge", text).group(0)
            break
    return {"challenge_name": challenge}


def extract_challenge_page_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for element in [soup.find("h1"), soup.find("title")]:
        if not element:
            continue
        match = re.search(
            r"\b20\d{2}\s+BEHAVIOR Challenge\b",
            element.get_text(" ", strip=True),
        )
        if match:
            return match.group(0)
    return ""


def normalize_model(value: str) -> str:
    key = re.sub(r"\s+", " ", value.strip().casefold())
    return MODEL_ALIASES.get(key, value.strip())


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def parse_contributors(html: str, page_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    headings = {
        "core team": "Core Team",
        "supporting team": "Supporting Team",
        "alumni": "Alumni",
    }
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        group = headings.get(heading.get_text(" ", strip=True).casefold())
        if not group:
            continue
        category = heading.find_parent(class_="team-category")
        if category is not None:
            if group in {"Core Team", "Supporting Team"}:
                members = category.select(".team-member")
                for member in members:
                    name_tag = member.select_one(".team-name")
                    anchor = member.find("a", href=True)
                    name = name_tag.get_text(" ", strip=True) if name_tag else ""
                    key = normalize_name(name)
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "name": name,
                            "group": group,
                            "homepage": anchor.get("href", "") if anchor else "",
                            "source_url": page_url,
                        }
                    )
            else:
                for member in category.select(".alumni-name"):
                    name = member.get_text(" ", strip=True)
                    key = normalize_name(name)
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "name": name,
                            "group": group,
                            "homepage": member.get("href", "") if member.name == "a" else "",
                            "source_url": page_url,
                        }
                    )
            continue
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and re.fullmatch(r"h[1-6]", sibling.name or ""):
                break
            if not isinstance(sibling, Tag):
                continue
            for anchor in sibling.find_all("a", href=True):
                name = anchor.get_text(" ", strip=True)
                key = normalize_name(name)
                if not key or key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "name": name,
                        "group": group,
                        "homepage": anchor.get("href", ""),
                        "source_url": page_url,
                    }
                )
    return rows


def expand_paper_records(
    papers: Iterable[dict[str, Any]],
    contributors: Iterable[dict[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    roster = {normalize_name(row["name"]): row for row in contributors}
    verified: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    keys: set[tuple[str, str, str, str]] = set()

    for paper in papers:
        year = int(paper["year"])
        if not YEAR_MIN <= year <= YEAR_MAX:
            continue
        paper_id = paper.get("doi") or paper.get("arxiv_id") or normalize_title(paper["title"])
        models = paper.get("models", [])
        for author in paper.get("authors", []):
            roster_entry = roster.get(normalize_name(author["name"]))
            if roster_entry is None:
                continue
            if not models:
                unresolved.append(
                    {
                        "person": roster_entry["name"],
                        "contributor_group": roster_entry["group"],
                        "homepage": roster_entry["homepage"],
                        "paper": paper["title"],
                        "year": year,
                        "paper_url": paper["paper_url"],
                        "doi": paper.get("doi", ""),
                        "arxiv_id": paper.get("arxiv_id", ""),
                        "verification_status": paper.get("verification_status", "unknown"),
                        "model_note": paper.get("model_note", "具体型号未披露"),
                    }
                )
                continue
            for model in models:
                raw_model = model["model"]
                canonical = normalize_model(raw_model)
                key = (normalize_name(author["name"]), str(paper_id), canonical, model["entity_type"])
                if key in keys:
                    continue
                keys.add(key)
                verified.append(
                    {
                        "person": roster_entry["name"],
                        "contributor_group": roster_entry["group"],
                        "homepage": roster_entry["homepage"],
                        "paper": paper["title"],
                        "year": year,
                        "paper_url": paper["paper_url"],
                        "project_url": paper.get("project_url", ""),
                        "doi": paper.get("doi", ""),
                        "arxiv_id": paper.get("arxiv_id", ""),
                        "model_raw": raw_model,
                        "model_canonical": canonical,
                        "entity_type": model["entity_type"],
                        "robot_type": model.get("robot_type", ""),
                        "arm_model": normalize_model(model.get("arm_model", ""))
                        if model.get("arm_model")
                        else "",
                        "end_effector": model.get("end_effector", ""),
                        "usage_context": model.get("usage_context", ""),
                        "world": model.get("world", ""),
                        "evidence": model["evidence"],
                        "evidence_url": model.get("evidence_url", paper.get("project_url", "")),
                        "evidence_location": model.get("evidence_location", ""),
                        "verification_status": model.get("verification_status", "verified"),
                    }
                )

    return pd.DataFrame(verified), pd.DataFrame(unresolved)


def model_statistics(records: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "entity_type",
        "model",
        "record_count",
        "unique_people",
        "unique_papers",
        "rank_within_type",
    ]
    if records.empty:
        return pd.DataFrame(columns=columns)

    frames: list[pd.DataFrame] = []
    verified = records[records["verification_status"] == "verified"]
    dimensions = {
        "robot": "model_canonical",
        "arm": "arm_model",
        "end_effector": "end_effector",
    }
    for entity_type, model_column in dimensions.items():
        group = verified[verified[model_column].fillna("").astype(str).str.strip() != ""]
        if group.empty:
            continue
        stats = (
            group.groupby(model_column, as_index=False)
            .agg(
                record_count=("person", "size"),
                unique_people=("person", "nunique"),
                unique_papers=("paper", "nunique"),
            )
            .rename(columns={model_column: "model"})
            .sort_values(
                ["record_count", "unique_people", "unique_papers", "model"],
                ascending=[False, False, False, True],
            )
        )
        stats.insert(0, "entity_type", entity_type)
        stats["rank_within_type"] = range(1, len(stats) + 1)
        frames.append(stats)
    return pd.concat(frames, ignore_index=True)[columns]


def candidate_is_robotics(work: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(work.get("title", work.get("paper", ""))),
            str(work.get("abstract", "")),
            " ".join(str(value) for value in work.get("topics", [])),
        ]
    ).casefold()
    terms = (
        "robot",
        "manipulation",
        "grasp",
        "embodied",
        "teleoperation",
        "visuomotor",
        "locomotion",
    )
    return any(term in text for term in terms)
