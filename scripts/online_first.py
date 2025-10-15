#!/usr/bin/env python3
"""Fetch recently accepted papers for finance and accounting journals.

This script retrieves the latest "online first" or "publish ahead of print"
articles from a mix of publishers and writes them to a JSON file that can be
consumed by the Jekyll site.

Usage
-----
python scripts/online_first.py --config _data/journal_sources.json --output _data/online_first.json

The configuration file contains a list of journal sources with the metadata
required by each scraper. Each scraper is identified by the "type" key in the
configuration entry. Most publishers require slightly different parsing logic,
so we keep the code organized by provider-specific helpers.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover - optional dependency for offline mode
    BeautifulSoup = None  # type: ignore


LOGGER = logging.getLogger("online_first")
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_3) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
    ),
    "Accept-Language": "en-US,en;q=0.8",
}


@dataclass
class Article:
    """Normalized representation of an article."""

    title: str
    url: str
    authors: str = ""
    date: str = ""

    def to_dict(self, journal_code: str, source_name: str) -> Dict[str, str]:
        return {
            "journal": journal_code,
            "source": source_name,
            "title": self.title,
            "authors": self.authors,
            "date": self.date,
            "url": self.url,
        }


class ScraperError(RuntimeError):
    """Raised when a scraper cannot parse the upstream payload."""


def _load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _strip_text(node: Optional[BeautifulSoup], separator: str = ", ") -> str:
    if not node:
        return ""
    text = node.get_text(separator, strip=True)
    return text.strip()


def _coerce_authors(raw: Optional[Iterable]) -> str:
    if not raw:
        return ""
    names: List[str] = []
    for item in raw:
        if isinstance(item, dict):
            name = item.get("fullName") or item.get("name") or item.get("preferredName")
        else:
            name = str(item)
        if name:
            names.append(name.strip())
    return "; ".join(names)


def _fetch_html(session: requests.Session, url: str) -> BeautifulSoup:
    if BeautifulSoup is None:  # pragma: no cover - runtime guard for optional import
        raise ImportError("beautifulsoup4 is required to fetch remote HTML content")
    LOGGER.debug("Fetching HTML from %s", url)
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def scrape_sciencedirect(session: requests.Session, source: Dict, *, max_items: Optional[int] = None) -> List[Article]:
    """Parse ScienceDirect (Elsevier) article listings.

    We rely on the JSON payload embedded in the Next.js "__NEXT_DATA__" script
    tag. The structure changes occasionally, so the parser takes a defensive
    approach and supports multiple fallbacks for the relevant fields.
    """

    soup = _fetch_html(session, source["url"])
    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag or not script_tag.string:
        raise ScraperError("ScienceDirect payload did not include __NEXT_DATA__")

    data = json.loads(script_tag.string)
    page_props = data.get("props", {}).get("pageProps", {})
    containers: List = []
    for key in ("pageData", "content", "results", "searchResults"):
        value = page_props.get(key)
        if isinstance(value, list):
            containers.extend(value)
        elif isinstance(value, dict):
            # ScienceDirect often nests results under `pageData.results`.
            for inner_key in ("results", "articles", "items"):
                inner = value.get(inner_key)
                if isinstance(inner, list):
                    containers.extend(inner)
    if not containers:
        raise ScraperError("ScienceDirect payload did not contain a results list")

    articles: List[Article] = []
    base_url = source.get("base_url", "https://www.sciencedirect.com")
    for record in containers:
        candidate = record.get("article") if isinstance(record, dict) else None
        if not candidate and isinstance(record, dict):
            candidate = record
        if not isinstance(candidate, dict):
            continue

        title = (
            candidate.get("title")
            or candidate.get("titleFull")
            or candidate.get("publicationTitle")
            or candidate.get("displayTitle")
        )
        uri = candidate.get("uri") or candidate.get("url") or candidate.get("href")
        if not title or not uri:
            continue
        if uri.startswith("/"):
            uri = urljoin(base_url, uri)

        authors = candidate.get("authors") or candidate.get("creators")
        authors_str = _coerce_authors(authors)
        date_value = (
            candidate.get("publicationDate")
            or candidate.get("availableDate")
            or candidate.get("coverDate")
            or candidate.get("articleFirstAvailableDate")
        )

        articles.append(Article(title=title.strip(), url=uri, authors=authors_str, date=(date_value or "")))
        if max_items and len(articles) >= max_items:
            break

    return articles


def scrape_oup(session: requests.Session, source: Dict, *, max_items: Optional[int] = None) -> List[Article]:
    """Parse Oxford University Press "advance article" listings."""

    soup = _fetch_html(session, source["url"])
    items = soup.select("article.al-article-item, div.al-article-item")
    if not items:
        # Fall back to more generic selectors that still cover the same markup.
        items = soup.select("li.widget-items__item article, div.widget-items__content article")
    if not items:
        raise ScraperError("OUP page did not return recognizable article markup")

    base_url = source.get("base_url", "https://academic.oup.com")
    articles: List[Article] = []
    for article_node in items:
        title_tag = article_node.select_one("h3 a, h4 a, h5 a")
        if not title_tag or not title_tag.get_text(strip=True):
            continue
        title = title_tag.get_text(strip=True)
        link = title_tag.get("href") or ""
        if not link:
            continue
        link = urljoin(base_url, link)

        authors = article_node.select_one(".al-article-item__authors, .al-authors-list, .search-result__authors")
        authors_text = _strip_text(authors, "; ")
        date_tag = article_node.select_one(".al-article-item__date, .citation__date, time")
        date_text = _strip_text(date_tag)

        articles.append(Article(title=title, url=link, authors=authors_text, date=date_text))
        if max_items and len(articles) >= max_items:
            break

    return articles


def scrape_wiley(session: requests.Session, source: Dict, *, max_items: Optional[int] = None) -> List[Article]:
    """Parse Wiley Online Library "Early View" listings."""

    soup = _fetch_html(session, source["url"])
    script_tag = soup.find("script", id="__NEXT_DATA__")
    base_url = source.get("base_url", "https://onlinelibrary.wiley.com")
    articles: List[Article] = []

    if script_tag and script_tag.string:
        data = json.loads(script_tag.string)
        page_props = data.get("props", {}).get("pageProps", {})
        containers = []
        for key in ("content", "pageData", "data"):
            value = page_props.get(key)
            if isinstance(value, dict):
                for inner_key in ("listing", "results", "items"):
                    inner = value.get(inner_key)
                    if isinstance(inner, list):
                        containers.extend(inner)
            elif isinstance(value, list):
                containers.extend(value)
        for entry in containers:
            content = entry.get("content") if isinstance(entry, dict) else None
            if not content and isinstance(entry, dict):
                content = entry
            if not isinstance(content, dict):
                continue
            title = content.get("title") or content.get("headline")
            link = content.get("url") or content.get("link")
            if not title or not link:
                continue
            link = urljoin(base_url, link)
            authors = content.get("authors") or content.get("contributors")
            authors_text = _coerce_authors(authors)
            date_text = content.get("publicationDate") or content.get("coverDate") or content.get("date") or ""
            articles.append(Article(title=title.strip(), url=link, authors=authors_text, date=date_text))
            if max_items and len(articles) >= max_items:
                break

    if articles:
        return articles

    # Fallback to HTML parsing if the JSON payload was missing or unexpected.
    items = soup.select("div.issue-item, div.card")
    for item in items:
        title_tag = item.select_one("h3 a, h2 a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        link = urljoin(base_url, title_tag.get("href", ""))
        authors = item.select_one("ul.author-list, div.card__contributors, p.article-contributor")
        authors_text = _strip_text(authors, "; ")
        date_tag = item.select_one("span.pub-date, span.epub-date, time")
        date_text = _strip_text(date_tag)
        articles.append(Article(title=title, url=link, authors=authors_text, date=date_text))
        if max_items and len(articles) >= max_items:
            break

    if not articles:
        raise ScraperError("Wiley page did not return recognizable article markup")

    return articles


def scrape_aaahq(session: requests.Session, source: Dict, *, max_items: Optional[int] = None) -> List[Article]:
    """Parse The Accounting Review (AAAHQ) publish-ahead-of-print page."""

    soup = _fetch_html(session, source["url"])
    items = soup.select("article.citation, div.issue-item")
    if not items:
        items = soup.select("li.issue-item")
    if not items:
        raise ScraperError("AAAHQ page did not return recognizable article markup")

    base_url = source.get("base_url", "https://publications.aaahq.org")
    articles: List[Article] = []
    for node in items:
        title_tag = node.select_one("h3 a, h2 a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        link = urljoin(base_url, title_tag.get("href", ""))
        authors_tag = node.select_one("div.citation__authors, p.card-author, p.article-contributor")
        authors_text = _strip_text(authors_tag, "; ")
        date_tag = node.select_one("span.pub-date, time, div.citation__date")
        date_text = _strip_text(date_tag)
        articles.append(Article(title=title, url=link, authors=authors_text, date=date_text))
        if max_items and len(articles) >= max_items:
            break

    return articles


def scrape_springer(session: requests.Session, source: Dict, *, max_items: Optional[int] = None) -> List[Article]:
    """Parse Springer Online First listings."""

    soup = _fetch_html(session, source["url"])
    items = soup.select("li.app-article-list__item, li.c-list-group__item, article")
    if not items:
        items = soup.select("ol.c-list-group li")
    if not items:
        raise ScraperError("Springer page did not return recognizable article markup")

    base_url = source.get("base_url", "https://link.springer.com")
    articles: List[Article] = []
    for node in items:
        title_tag = node.select_one("h3 a, h2 a, p.title a")
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        link = urljoin(base_url, title_tag.get("href", ""))
        authors_tag = node.select_one("p.authors, ul.c-author-list, span.app-article-list__authors")
        authors_text = _strip_text(authors_tag, "; ")
        date_tag = node.select_one("time, span.app-article-list__published, span.c-meta__item")
        date_text = _strip_text(date_tag)
        articles.append(Article(title=title, url=link, authors=authors_text, date=date_text))
        if max_items and len(articles) >= max_items:
            break

    return articles


SCRAPERS: Dict[str, Callable[[requests.Session, Dict], List[Article]]] = {
    "sciencedirect": scrape_sciencedirect,
    "oup": scrape_oup,
    "wiley": scrape_wiley,
    "aaahq": scrape_aaahq,
    "springer": scrape_springer,
}


def _articles_from_entries(entries: Iterable[Dict[str, str]], *, max_items: Optional[int] = None) -> List[Article]:
    """Create :class:`Article` objects from static entry dictionaries."""

    articles: List[Article] = []
    for entry in entries or []:
        title = entry.get("title") if isinstance(entry, dict) else None
        url = entry.get("url") if isinstance(entry, dict) else None
        if not title or not url:
            continue

        article = Article(
            title=title,
            url=url,
            authors=entry.get("authors", "") if isinstance(entry, dict) else "",
            date=entry.get("date", "") if isinstance(entry, dict) else "",
        )
        articles.append(article)
        if max_items and len(articles) >= max_items:
            break

    return articles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch online-first journal articles")
    parser.add_argument("--config", default="_data/journal_sources.json", help="Path to the journal configuration file")
    parser.add_argument("--output", default="_data/online_first.json", help="Output JSON file for the aggregated results")
    parser.add_argument("--max-per-source", type=int, default=0, help="Optional limit for the number of items per journal")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use offline fixtures defined in the config instead of performing network requests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    config_path = Path(args.config)
    if not config_path.exists():
        LOGGER.error("Config file not found: %s", config_path)
        return 1

    config = _load_json(config_path)
    sources = config.get("sources") if isinstance(config, dict) else None
    if sources is None:
        LOGGER.error("Config file must contain a 'sources' list")
        return 1

    session: Optional[requests.Session] = None
    if not args.offline:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)

    aggregated: List[Dict[str, str]] = []
    errors: List[str] = []
    limit = args.max_per_source if args.max_per_source > 0 else None

    for source in sources:
        code = source.get("code")
        name = source.get("name") or code or "Unknown"
        scraper_key = source.get("type")
        scraper = SCRAPERS.get(scraper_key)
        offline_entries = _articles_from_entries(source.get("offline_entries"), max_items=limit)

        if args.offline:
            if offline_entries:
                LOGGER.info("Using offline fixtures for %s (%s)", name, code)
                for article in offline_entries:
                    aggregated.append(article.to_dict(code or name, name))
            else:
                message = f"No offline fixtures configured for {name}"
                LOGGER.error(message)
                errors.append(message)
            continue

        if not scraper:
            message = f"No scraper registered for type '{scraper_key}' (journal: {name})"
            LOGGER.error(message)
            errors.append(message)
            continue

        LOGGER.info("Fetching %s (%s)", name, code)
        try:
            results = scraper(session, source, max_items=limit)
        except Exception as exc:  # pylint: disable=broad-except
            if offline_entries:
                message = f"{name}: {exc}; using offline fixtures"
                LOGGER.warning(message)
                errors.append(message)
                for article in offline_entries:
                    aggregated.append(article.to_dict(code or name, name))
                continue

            message = f"{name}: {exc}"
            LOGGER.exception("Failed to fetch %s", name)
            errors.append(message)
            continue

        for article in results:
            aggregated.append(article.to_dict(code or name, name))

    aggregated.sort(key=lambda item: (item.get("date") or "", item.get("title") or ""), reverse=True)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "entries": aggregated,
    }
    if errors:
        payload["errors"] = errors
        LOGGER.warning("Completed with %d error(s)", len(errors))
    else:
        LOGGER.info("Successfully fetched %d articles", len(aggregated))

    output_path = Path(args.output)
    _write_json(output_path, payload)
    LOGGER.info("Wrote %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
