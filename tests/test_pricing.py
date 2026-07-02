import json
from pathlib import Path

import pandas as pd

from behavior_reader.pricing import (
    build_price_frame,
    format_cny_price,
    format_original_price,
)


ROOT = Path(__file__).resolve().parents[1]


def test_numeric_and_quote_prices_are_handled_separately() -> None:
    catalog = {
        "snapshot_date": "2026-07-02",
        "exchange_rates": {
            "USD": {
                "rate_to_cny": 7.0,
                "rate_date": "2026-07-01",
                "source_url": "https://rates",
            }
        },
        "quotes": [
            {
                "behavior_model": "A",
                "price_kind": "range",
                "currency": "USD",
                "price_min": 10,
                "price_max": 20,
            },
            {
                "behavior_model": "B",
                "price_kind": "quote",
                "currency": "",
                "price_min": None,
                "price_max": None,
            },
        ],
    }

    frame = build_price_frame(catalog)

    assert frame.loc[0, "cny_min"] == 70
    assert frame.loc[0, "cny_max"] == 140
    assert pd.isna(frame.loc[1, "cny_min"])
    assert format_original_price(frame.iloc[0]) == "USD 10.00–20.00"
    assert format_cny_price(frame.iloc[0]) == "¥70–¥140"
    assert format_original_price(frame.iloc[1]) == "询价"


def test_price_catalog_covers_every_website_model_without_unitree_mixup() -> None:
    catalog = json.loads(
        (ROOT / "data" / "price_catalog.json").read_text(encoding="utf-8")
    )
    website = pd.read_csv(ROOT / "reports" / "website_robot_models.csv")
    frame = build_price_frame(catalog)

    assert set(website["model"]) == set(frame["behavior_model"])
    assert len(frame["behavior_model"].unique()) == 14
    identity_columns = frame[["behavior_model", "sold_model"]]
    assert not identity_columns.astype(str).apply(
        lambda column: column.str.contains("Unitree", case=False).any()
    ).any()


def test_every_numeric_price_has_source_currency_and_rate() -> None:
    catalog = json.loads(
        (ROOT / "data" / "price_catalog.json").read_text(encoding="utf-8")
    )
    frame = build_price_frame(catalog)
    numeric = frame[frame["price_kind"].isin({"fixed", "from", "range", "approx"})]
    non_numeric = frame[
        ~frame["price_kind"].isin({"fixed", "from", "range", "approx"})
    ]

    assert numeric["source_url"].str.startswith("http").all()
    assert numeric["currency"].ne("").all()
    assert numeric["exchange_rate_to_cny"].notna().all()
    assert numeric["cny_min"].notna().all()
    assert non_numeric["cny_min"].isna().all()


def test_price_catalog_excludes_second_hand_quotes() -> None:
    catalog = json.loads(
        (ROOT / "data" / "price_catalog.json").read_text(encoding="utf-8")
    )
    for quote in catalog["quotes"]:
        assert "used" not in quote["condition"].casefold()
        assert "second-hand" not in quote["condition"].casefold()
        assert quote["source_type"].casefold() != "secondary marketplace"


def test_currency_conversion_uses_decimal_rounding() -> None:
    assert build_price_frame(
        {
            "snapshot_date": "2026-07-02",
            "exchange_rates": {
                "USD": {
                    "rate_to_cny": 6.7945,
                    "rate_date": "2026-07-01",
                    "source_url": "https://rates",
                }
            },
            "quotes": [
                {
                    "behavior_model": "Stretch",
                    "price_kind": "fixed",
                    "currency": "USD",
                    "price_min": 24950,
                    "price_max": 24950,
                }
            ],
        }
    ).iloc[0]["cny_min"] == 169522.78
