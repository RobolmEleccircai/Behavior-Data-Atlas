from __future__ import annotations

import argparse
from pathlib import Path

from behavior_reader.validation import collect_urls, validate_urls


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
INPUTS = (
    REPORTS / "resources.csv",
    REPORTS / "website_robot_models.csv",
    REPORTS / "contributor_paper_robots.csv",
    REPORTS / "robot_prices.csv",
)
OUTPUT = REPORTS / "link_validation.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate links used by the final reports.")
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    result = validate_urls(
        collect_urls(INPUTS),
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
    )
    result.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    failures = result[~result["ok"]]
    print(f"checked={len(result)} ok={len(result) - len(failures)} failed={len(failures)}")
    print(f"output={OUTPUT}")
    if not failures.empty:
        print(failures[["status_code", "url", "error"]].to_string(index=False))
        if args.strict:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
