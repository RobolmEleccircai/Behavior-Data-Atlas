from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


def write_outputs(
    pages: Iterable[dict[str, Any]],
    output_root: Path,
) -> tuple[Path, Path]:
    records = list(pages)
    raw_dir = output_root / "raw"
    processed_dir = output_root / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = raw_dir / "pages.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    csv_path = processed_dir / "pages.csv"
    summaries = [
        {
            "url": record["url"],
            "title": record["title"],
            "description": record["description"],
            "text_length": len(record["text"]),
            "link_count": len(record["links"]),
            "fetched_at": record["fetched_at"],
        }
        for record in records
    ]
    pd.DataFrame(
        summaries,
        columns=[
            "url",
            "title",
            "description",
            "text_length",
            "link_count",
            "fetched_at",
        ],
    ).to_csv(csv_path, index=False, encoding="utf-8-sig")
    return jsonl_path, csv_path

