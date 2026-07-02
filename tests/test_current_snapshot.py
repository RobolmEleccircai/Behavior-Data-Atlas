import json
from pathlib import Path

import pandas as pd
import pytest

from behavior_reader.research import parse_contributors


ROOT = Path(__file__).resolve().parents[1]
HOMEPAGE = ROOT / "data" / "raw" / "homepage.html"
ROBOT_IMAGES = ROOT / "reports" / "assets" / "robots"


@pytest.mark.skipif(not HOMEPAGE.exists(), reason="Run collect_research first")
def test_saved_current_homepage_has_expected_roster() -> None:
    rows = parse_contributors(
        HOMEPAGE.read_text(encoding="utf-8"),
        "https://behavior.stanford.edu/",
    )
    counts = {
        group: sum(row["group"] == group for row in rows)
        for group in ("Core Team", "Supporting Team", "Alumni")
    }

    assert len(rows) == 57
    assert counts == {"Core Team": 15, "Supporting Team": 11, "Alumni": 31}


def test_catalog_uses_current_resource_paths() -> None:
    catalog = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    urls = {row["url"] for row in catalog["resources"]}
    required = {
        "https://behavior.stanford.edu/behavior_components/behavior_tasks.html",
        "https://behavior.stanford.edu/behavior_components/scenes.html",
        "https://behavior.stanford.edu/behavior_components/objects.html",
        "https://behavior.stanford.edu/behavior_components/joylo.html",
        "https://behavior.stanford.edu/behavior_100/overview.html",
        "https://behavior.stanford.edu/behavior_100/dataset.html",
    }

    assert required <= urls


def test_all_website_models_have_downloaded_official_images() -> None:
    robots = pd.read_csv(ROOT / "reports" / "website_robot_models.csv")

    assert robots["image_path"].notna().all()
    assert robots["image_source_url"].str.startswith(
        "https://behavior.stanford.edu/assets/robots/"
    ).all()
    assert all((ROOT / "reports" / path).is_file() for path in robots["image_path"])
