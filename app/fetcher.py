from __future__ import annotations

from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse


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


def fetch_paginated_documents(start_url: str, max_pages: int = 3, timeout: int = 20) -> list[tuple[str, str, str]]:
    """
    Follow pagination links and return [(url, title, text)].
    """
    if max_pages < 1:
        return []

    host = urlparse(start_url).netloc
    current = start_url
    visited: set[str] = set()
    results: list[tuple[str, str, str]] = []

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
        title = soup.title.get_text(strip=True) if soup.title else current
        text = soup.get_text(" ", strip=True)
        if len(text) > 20000:
            text = text[:20000]
        results.append((current, title[:512], text))

        next_url = _find_next_page_url(soup, current, host)
        if not next_url or next_url in visited:
            break
        current = next_url

    return results
