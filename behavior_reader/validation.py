from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Iterable

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .crawler import USER_AGENT


URL_COLUMNS = (
    "url",
    "evidence_url",
    "manufacturer_evidence_url",
    "arm_evidence_url",
    "end_effector_evidence_url",
    "paper_url",
    "project_url",
    "source_url",
    "exchange_rate_source",
    "image_source_url",
)


def collect_urls(paths: Iterable[Path]) -> list[str]:
    urls: set[str] = set()
    for path in paths:
        frame = pd.read_csv(path)
        for column in URL_COLUMNS:
            if column not in frame:
                continue
            urls.update(
                value.strip()
                for value in frame[column].dropna().astype(str)
                if value.strip().startswith(("http://", "https://"))
            )
    return sorted(urls)


def validate_urls(
    urls: Iterable[str],
    delay_seconds: float = 0.25,
    timeout_seconds: float = 20.0,
) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=2,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    checked_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, object]] = []
    for url in urls:
        try:
            response = session.get(url, timeout=timeout_seconds, allow_redirects=True)
            rows.append(
                {
                    "url": url,
                    "status_code": response.status_code,
                    "ok": 200 <= response.status_code < 400,
                    "final_url": response.url,
                    "checked_at": checked_at,
                    "error": "",
                }
            )
        except requests.RequestException as exc:
            rows.append(
                {
                    "url": url,
                    "status_code": "",
                    "ok": False,
                    "final_url": "",
                    "checked_at": checked_at,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        time.sleep(delay_seconds)
    return pd.DataFrame(
        rows,
        columns=["url", "status_code", "ok", "final_url", "checked_at", "error"],
    )
