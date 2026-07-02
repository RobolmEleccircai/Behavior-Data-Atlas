from __future__ import annotations

import argparse
from pathlib import Path

from .crawler import CrawlConfig, crawl
from .storage import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read public pages from behavior.stanford.edu.",
    )
    parser.add_argument(
        "--start-url",
        default="https://behavior.stanford.edu/",
        help="First page to visit (default: %(default)s)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum number of HTML pages to save (default: %(default)s)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Minimum seconds between requests (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Output root directory (default: %(default)s)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = CrawlConfig(
        start_url=args.start_url,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
    )
    pages = crawl(config)
    jsonl_path, csv_path = write_outputs(pages, args.output_dir)
    print(f"Saved {len(pages)} pages")
    print(f"JSONL: {jsonl_path}")
    print(f"CSV:   {csv_path}")


if __name__ == "__main__":
    main()

