from __future__ import annotations

import logging
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


def fetch_document(url: str, timeout: int = 20) -> tuple[str, str]:
    """
    Fetch a URL and return (title, plain_text).
    """
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "amlredflags-v2/1.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else url
    text = soup.get_text(" ", strip=True)

    # Keep payload bounded for predictable DB/storage behavior.
    if len(text) > 20000:
        text = text[:20000]

    return title[:512], text


def _is_same_host(url: str, host: str) -> bool:
    try:
        return urlparse(url).netloc == host
    except Exception:
        return False


def _find_next_page_url(soup: BeautifulSoup, current_url: str, host: str) -> str | None:
    # First preference: explicit rel=next links.
    rel_next = soup.select('a[rel~="next"]')
    for anchor in rel_next:
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        candidate = urljoin(current_url, href)
        if _is_same_host(candidate, host):
            return candidate

    # Fallback: common "next page" labels.
    next_labels = {"next", "older", ">", ">>", "›", "»", "next page"}
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True).lower()
        if label not in next_labels and not label.startswith("next"):
            continue
        candidate = urljoin(current_url, anchor["href"])
        if _is_same_host(candidate, host):
            return candidate

    return None


def _normalize_link(current_url: str, href: str) -> str | None:
    href = (href or "").strip()
    if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
        return None
    absolute = urljoin(current_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    # Drop fragments so duplicates collapse cleanly.
    return absolute.split("#", 1)[0]


def _looks_like_listing_or_nav_link(candidate_url: str) -> bool:
    parsed = urlparse(candidate_url)
    path = parsed.path.lower()
    if path in {"", "/"}:
        return True
    nav_tokens = (
        "/news",
        "/news/",
        "/news-events",
        "/news-events/newsroom",
        "/enforcement-actions",
    )
    return path in nav_tokens


def _extract_article_links(soup: BeautifulSoup, current_url: str, host: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        candidate = _normalize_link(current_url, anchor.get("href", ""))
        if not candidate:
            continue
        if not _is_same_host(candidate, host):
            continue
        if candidate == current_url:
            continue
        if _looks_like_listing_or_nav_link(candidate):
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        links.append(candidate)

    return links


def fetch_paginated_documents(
    start_url: str,
    max_pages: int = 3,
    max_articles: int = 30,
    timeout: int = 20,
) -> list[tuple[str, str, str]]:
    """
    Follow listing-page pagination, extract article links, and return
    [(article_url, title, text)].
    """
    if max_pages < 1 or max_articles < 1:
        return []

    host = urlparse(start_url).netloc
    current = start_url
    visited: set[str] = set()
    article_urls: list[str] = []
    seen_articles: set[str] = set()

    for _ in range(max_pages):
        if current in visited:
            break
        visited.add(current)

        response = requests.get(
            current,
            timeout=timeout,
            headers={"User-Agent": "amlredflags-v2/1.0"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for link in _extract_article_links(soup, current, host):
            if link in seen_articles:
                continue
            seen_articles.add(link)
            article_urls.append(link)
            if len(article_urls) >= max_articles:
                break

        next_url = _find_next_page_url(soup, current, host)
        if len(article_urls) >= max_articles:
            break
        if not next_url or next_url in visited:
            break
        current = next_url

    results: list[tuple[str, str, str]] = []
    for article_url in article_urls[:max_articles]:
        try:
            title, text = fetch_document(article_url, timeout=timeout)
            results.append((article_url, title, text))
        except Exception as exc:
            logger.warning("Skipping article fetch failure for %s: %s", article_url, exc)

    return results
