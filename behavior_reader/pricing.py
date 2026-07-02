from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd


NUMERIC_PRICE_KINDS = {"fixed", "from", "range", "approx"}


def convert_to_cny(value: Any, rate: Any) -> float:
    return float(
        (Decimal(str(value)) * Decimal(str(rate))).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


def build_price_frame(catalog: dict[str, Any]) -> pd.DataFrame:
    rates = catalog["exchange_rates"]
    rows: list[dict[str, Any]] = []
    for quote in catalog["quotes"]:
        row = dict(quote)
        currency = row.get("currency", "")
        rate_info = rates.get(currency, {})
        rate = rate_info.get("rate_to_cny")
        is_numeric = (
            row["price_kind"] in NUMERIC_PRICE_KINDS
            and row.get("price_min") is not None
            and rate is not None
        )
        row["exchange_rate_to_cny"] = rate if is_numeric else None
        row["exchange_rate_date"] = rate_info.get("rate_date", "") if is_numeric else ""
        row["exchange_rate_source"] = (
            rate_info.get("source_url", "") if is_numeric else ""
        )
        row["cny_min"] = (
            convert_to_cny(row["price_min"], rate) if is_numeric else None
        )
        row["cny_max"] = (
            convert_to_cny(row["price_max"], rate)
            if is_numeric and row.get("price_max") is not None
            else None
        )
        row["observed_at"] = catalog["snapshot_date"]
        rows.append(row)
    return pd.DataFrame(rows)


def format_original_price(row: pd.Series) -> str:
    if row["price_kind"] in {"quote", "no_public_price", "not_for_sale"}:
        return {
            "quote": "询价",
            "no_public_price": "无公开价格",
            "not_for_sale": "非商品",
        }[row["price_kind"]]
    low = f"{row['price_min']:,.2f}"
    high = f"{row['price_max']:,.2f}"
    if row["price_kind"] == "range" and row["price_min"] != row["price_max"]:
        return f"{row['currency']} {low}–{high}"
    prefix = {"from": "起价 ", "approx": "约 "}.get(row["price_kind"], "")
    return f"{prefix}{row['currency']} {low}"


def format_cny_price(row: pd.Series) -> str:
    if pd.isna(row.get("cny_min")):
        return ""
    if row["price_kind"] == "range" and row["cny_min"] != row["cny_max"]:
        return f"¥{row['cny_min']:,.0f}–¥{row['cny_max']:,.0f}"
    prefix = "约 " if row["price_kind"] in NUMERIC_PRICE_KINDS else ""
    return f"{prefix}¥{row['cny_min']:,.0f}"
