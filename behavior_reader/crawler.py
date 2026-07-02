from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests


LOGGER = logging.getLogger(__name__)
USER_AGENT = "BehaviorResearchReader/0.1 (+public academic website reader)"


@dataclass(frozen=True)
class CrawlConfig:
    start_url: str = "https://behavior.stanford.edu/"
    max_pages: int = 10
    delay_seconds: float = 1.5
    timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        if self.max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds cannot be negative")
        parsed = urlparse(self.start_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("start_url must be an absolute HTTP(S) URL")


def normalize_url(base_url: str, href: str) -> str | None:
    absolute, _fragment = urldefrag(urljoin(base_url, href))
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    normalized_path = parsed.path or "/"
    if normalized_path.endswith("/index.html"):
        normalized_path = normalized_path[: -len("index.html")]
    return parsed._replace(path=normalized_path, fragment="").geturl()


def parse_page(html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = (
        str(description_tag.get("content", "")).strip()
        if description_tag
        else ""
    )
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = "\n".join(
        line for line in main.get_text("\n", strip=True).splitlines() if line
    )

    links: list[str] = []
    seen_links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        link = normalize_url(url, str(anchor["href"]))
        if link and link not in seen_links:
            seen_links.add(link)
            links.append(link)

    return {
        "url": url,
        "title": title,
        "description": description,
        "text": text,
        "links": links,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _robot_parser(session: requests.Session, start_url: str, timeout: float) -> RobotFileParser:
    parsed = urlparse(start_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser(robots_url)
    try:
        response = session.get(robots_url, timeout=timeout)
        if response.ok:
            parser.parse(response.text.splitlines())
        else:
            LOGGER.warning("robots.txt returned HTTP %s", response.status_code)
            parser.parse([])
    except requests.RequestException as exc:
        LOGGER.warning("Could not read robots.txt: %s", exc)
        parser.parse([])
    return parser


def crawl(config: CrawlConfig) -> list[dict[str, Any]]:
    origin = urlparse(config.start_url).netloc.lower()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html"})
    robots = _robot_parser(session, config.start_url, config.timeout_seconds)

    queue = deque([normalize_url(config.start_url, config.start_url)])
    queued = set(queue)
    visited: set[str] = set()
    pages: list[dict[str, Any]] = []
    last_request_at = 0.0

    while queue and len(pages) < config.max_pages:
        url = queue.popleft()
        if url is None or url in visited:
            continue
        visited.add(url)

        if not robots.can_fetch(USER_AGENT, url):
            LOGGER.info("Skipped by robots.txt: %s", url)
            continue

        remaining_delay = config.delay_seconds - (time.monotonic() - last_request_at)
        if remaining_delay > 0:
            time.sleep(remaining_delay)

        try:
            response = session.get(url, timeout=config.timeout_seconds)
            last_request_at = time.monotonic()
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("Failed to read %s: %s", url, exc)
            continue

        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            continue

        page = parse_page(response.text, response.url)
        pages.append(page)
        for link in page["links"]:
            parsed_link = urlparse(link)
            if (
                parsed_link.netloc.lower() == origin
                and link not in visited
                and link not in queued
            ):
                queue.append(link)
                queued.add(link)

    return pages
