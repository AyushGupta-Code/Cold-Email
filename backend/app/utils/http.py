from __future__ import annotations

import re
import random
import time
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    return session


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timeout: int = 15,
    attempts: int = 3,
    delay_ms: int = 700,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                timeout=timeout,
                headers=headers,
            )
            response.raise_for_status()
            return response
        except Exception as exc:  # pragma: no cover - exercised indirectly
            last_error = exc
            if attempt == attempts:
                break
            time.sleep((delay_ms / 1000.0) * attempt)
    if last_error is None:
        raise RuntimeError("Unexpected request failure")
    raise last_error


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    return " ".join(soup.stripped_strings)


def normalize_result_url(url: str) -> str:
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and "uddg=" in parsed.query:
        params = parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return unquote(params["uddg"][0])
    if "search.yahoo.com" in parsed.netloc or "r.search.yahoo.com" in parsed.netloc:
        params = parse_qs(parsed.query)
        for key in ("RU", "ru", "url", "target"):
            if key in params and params[key]:
                return unquote(params[key][0])
        match = re.search(r"/RU=([^/]+)/RK=", parsed.path)
        if match:
            return unquote(match.group(1))
    return url


def fetch_public_page(url: str, use_playwright_fallback: bool = False) -> tuple[str, str]:
    session = create_session()
    try:
        response = request_with_retry(session, "GET", url, timeout=12)
        return response.text, "requests"
    except Exception:
        if not use_playwright_fallback:
            return "", "unavailable"
        try:  # pragma: no cover - optional dependency path
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=20000)
                content = page.content()
                browser.close()
                return content, "playwright"
        except Exception:
            return "", "unavailable"
