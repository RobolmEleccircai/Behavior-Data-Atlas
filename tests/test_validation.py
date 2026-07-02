from pathlib import Path

import pandas as pd

from behavior_reader.validation import collect_urls


def test_collect_urls_deduplicates_supported_columns(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    pd.DataFrame(
        {
            "url": ["https://example.com/a", "not-a-url"],
            "evidence_url": ["https://example.com/b", ""],
        }
    ).to_csv(first, index=False)
    pd.DataFrame(
        {
            "paper_url": ["https://example.com/a"],
            "manufacturer_evidence_url": ["https://example.com/c"],
        }
    ).to_csv(second, index=False)

    assert collect_urls([first, second]) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
