from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re

import pandas as pd

from behavior_reader.pricing import NUMERIC_PRICE_KINDS
from behavior_reader.research import model_statistics


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUTPUT = REPORTS / "report_audit.csv"


def main() -> None:
    report = (REPORTS / "report.md").read_text(encoding="utf-8")
    resources = pd.read_csv(REPORTS / "resources.csv")
    robots = pd.read_csv(REPORTS / "website_robot_models.csv")
    contributors = pd.read_csv(REPORTS / "contributors.csv")
    papers = pd.read_csv(REPORTS / "contributor_paper_robots.csv")
    candidates = pd.read_csv(REPORTS / "paper_candidates.csv")
    prices = pd.read_csv(REPORTS / "robot_prices.csv")
    saved_stats = pd.read_csv(REPORTS / "robot_model_statistics.csv")
    links = pd.read_csv(REPORTS / "link_validation.csv")

    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, evidence: str) -> None:
        checks.append(
            {"check": name, "passed": bool(passed), "evidence": evidence}
        )

    summary_expectations = {
        "网站资源": len(resources),
        "官网贡献者": len(contributors),
        "网站机器人页面实际整理出": len(robots),
        "已核验贡献者—论文—型号记录": len(papers),
        "待全文核验的贡献者—论文候选": len(candidates),
    }
    for label, value in summary_expectations.items():
        check(
            f"summary_{label}",
            bool(re.search(rf"{re.escape(label)}[^。\n]*\b{value}\b", report)),
            f"CSV={value}",
        )

    expected_stats = model_statistics(papers).reset_index(drop=True)
    comparable_columns = [
        "entity_type",
        "model",
        "record_count",
        "unique_people",
        "unique_papers",
        "rank_within_type",
    ]
    check(
        "model_statistics_recomputed",
        expected_stats[comparable_columns].equals(
            saved_stats[comparable_columns].reset_index(drop=True)
        ),
        f"rows={len(saved_stats)}",
    )
    check(
        "paper_records_unique",
        not papers.duplicated(["person", "paper", "model_canonical"]).any(),
        f"rows={len(papers)}",
    )
    check(
        "verified_records_have_evidence",
        papers["verification_status"].eq("verified").all()
        and papers["evidence_url"].notna().all()
        and papers["evidence_url"].ne("").all(),
        f"verified={papers['verification_status'].eq('verified').sum()}",
    )
    check(
        "paper_year_window",
        papers["year"].between(2022, 2026).all(),
        f"min={papers['year'].min()} max={papers['year'].max()}",
    )

    check(
        "price_model_coverage",
        set(prices["behavior_model"]) == set(robots["model"]),
        f"models={prices['behavior_model'].nunique()}",
    )
    condition_text = prices["condition"].fillna("").str.casefold()
    source_text = prices["source_type"].fillna("").str.casefold()
    check(
        "no_second_hand_prices",
        not condition_text.str.contains(r"\bused\b|second-hand").any()
        and not source_text.eq("secondary marketplace").any(),
        f"price_rows={len(prices)}",
    )

    conversion_errors: list[str] = []
    for row in prices.itertuples(index=False):
        if row.price_kind in NUMERIC_PRICE_KINDS:
            expected_min = (
                Decimal(str(row.price_min)) * Decimal(str(row.exchange_rate_to_cny))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            expected_max = (
                Decimal(str(row.price_max)) * Decimal(str(row.exchange_rate_to_cny))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if expected_min != Decimal(str(row.cny_min)) or expected_max != Decimal(
                str(row.cny_max)
            ):
                conversion_errors.append(row.sold_model)
        elif pd.notna(row.cny_min) or pd.notna(row.cny_max):
            conversion_errors.append(row.sold_model)
    check(
        "currency_conversion",
        not conversion_errors,
        "errors=" + ",".join(conversion_errors),
    )

    missing_images = [
        row.model
        for row in robots.itertuples(index=False)
        if not (REPORTS / row.image_path).is_file()
        or f'src="{row.image_path}"' not in report
    ]
    check(
        "robot_images_present",
        not missing_images,
        f"images={len(robots) - len(missing_images)}/{len(robots)}",
    )
    check(
        "validated_links",
        links["ok"].astype(str).str.casefold().eq("true").all(),
        f"ok={links['ok'].astype(str).str.casefold().eq('true').sum()}/{len(links)}",
    )

    result = pd.DataFrame(checks)
    result.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    failed = result[~result["passed"]]
    print(f"checks={len(result)} passed={len(result) - len(failed)} failed={len(failed)}")
    print(f"output={OUTPUT}")
    if not failed.empty:
        print(failed.to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
