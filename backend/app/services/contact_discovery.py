from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.api import ContactCandidate, JobSummary
from app.services.contact_ranker import is_recruiter_like_title, rank_contacts
from app.services.persistence import cache_search_results, get_cached_search
from app.services.us_filter import assess_us_location
from app.utils.http import create_session, fetch_public_page, normalize_result_url, request_with_retry
from app.utils.text import extract_email_addresses, normalize_company_name, normalize_whitespace, unique_preserve_order

SEARCH_PATTERNS = [
    "{company} recruiter United States linkedin",
    "{company} talent acquisition United States linkedin",
    "{company} hiring manager {position} United States",
    "{company} university recruiter United States",
    "{company} sourcer United States linkedin",
]

MOCK_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "sample_data" / "mock_search_results.json"
TARGET_DOMAINS = {"linkedin.com", "greenhouse.io", "lever.co"}


def discover_contacts(job_summary: JobSummary, db: Session, settings: Settings) -> tuple[list[ContactCandidate], list[str]]:
    warnings: list[str] = []
    queries = [pattern.format(company=job_summary.company_name, position=job_summary.position) for pattern in SEARCH_PATTERNS]
    raw_results: list[dict[str, str]] = []
    mode = settings.discovery_mode.lower()

    if mode not in {"live", "fallback", "mock"}:
        warnings.append(f"Unknown discovery mode '{settings.discovery_mode}', defaulting to live.")
        mode = "live"

    if mode != "mock":
        for query in queries:
            raw_results.extend(_search_duckduckgo(query, db, settings, warnings))
            time.sleep(settings.discovery_request_delay_ms / 1000.0)

    if mode == "mock" or (mode == "fallback" and not raw_results):
        fixture_results = _load_mock_results(job_summary.company_name)
        raw_results.extend(fixture_results)
        warnings.append("Using mock discovery data. Switch DISCOVERY_MODE=live for real public web discovery.")

    candidates = _extract_candidates(raw_results, job_summary, settings)
    candidates = deduplicate_contacts(candidates)
    ranked = rank_contacts(candidates, job_summary.company_name, job_summary.position, limit=settings.discovery_max_contacts)
    ranked = [candidate for candidate in ranked if candidate.is_us_based]

    if len(ranked) < settings.discovery_max_contacts:
        warnings.append(
            f"Only found {len(ranked)} US-based public contacts. Public search results were limited or lacked clear US evidence."
        )
    if ranked and not any(contact.public_email for contact in ranked):
        warnings.append("No verified public email addresses were found. Drafts are still available for manual outreach.")
    return ranked[: settings.discovery_max_contacts], warnings


def deduplicate_contacts(candidates: list[ContactCandidate]) -> list[ContactCandidate]:
    deduped: dict[str, ContactCandidate] = {}
    for candidate in candidates:
        key_parts = [
            normalize_whitespace(candidate.full_name).casefold(),
            normalize_company_name(candidate.company).casefold(),
        ]
        url = candidate.profile_url.casefold()
        key = "::".join(part for part in key_parts if part) or url
        existing = deduped.get(key)
        if not existing or candidate.score > existing.score or len(candidate.source_urls) > len(existing.source_urls):
            deduped[key] = candidate
    return list(deduped.values())


def extract_verified_public_email(*texts: str) -> str | None:
    matches: list[str] = []
    for text in texts:
        matches.extend(extract_email_addresses(text))
    return matches[0] if matches else None


def _search_duckduckgo(query: str, db: Session, settings: Settings, warnings: list[str]) -> list[dict[str, str]]:
    cached = get_cached_search(db, "duckduckgo_html", query)
    if cached is not None:
        return cached

    session = create_session()
    try:
        response = request_with_retry(
            session,
            "POST",
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            delay_ms=settings.discovery_request_delay_ms,
        )
        results = _parse_duckduckgo_results(response.text, limit=settings.discovery_max_results_per_query)
        if results:
            cache_search_results(db, "duckduckgo_html", query, results)
        return results
    except Exception as exc:
        warnings.append(f"Search query failed for '{query}': {exc}")
        return []


def _parse_duckduckgo_results(html: str, limit: int) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    for result in soup.select(".result"):
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if not link:
            continue
        url = normalize_result_url(link.get("href", ""))
        rows.append(
            {
                "title": normalize_whitespace(link.get_text(" ", strip=True)),
                "snippet": normalize_whitespace(snippet.get_text(" ", strip=True) if snippet else ""),
                "url": url,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _extract_candidates(raw_results: list[dict[str, str]], job_summary: JobSummary, settings: Settings) -> list[ContactCandidate]:
    company_key = normalize_company_name(job_summary.company_name).casefold()
    candidates: list[ContactCandidate] = []

    for row in raw_results:
        title = row.get("title", "")
        snippet = row.get("snippet", "")
        url = row.get("url", "")
        if not title or not url:
            continue

        combined_text = " ".join([title, snippet])
        company_match = company_key in combined_text.casefold()
        if not company_match and company_key.replace(" ", "") not in url.replace("-", "").casefold():
            continue

        full_name = _extract_name(title, snippet)
        role = _extract_title(title, snippet)
        if not full_name or not role:
            continue

        evidence = [item for item in [title, snippet] if item]
        location = _extract_location(combined_text)
        public_email = extract_verified_public_email(title, snippet)

        if not public_email and _should_fetch_page(url):
            page_html, method = fetch_public_page(url, use_playwright_fallback=settings.discovery_use_playwright_fallback)
            if page_html:
                page_text = BeautifulSoup(page_html, "lxml").get_text(" ", strip=True)
                public_email = extract_verified_public_email(page_text)
                richer_location = _extract_location(page_text)
                location = richer_location or location
                evidence.append(f"Fetched with {method}: {page_text[:220]}")

        is_us, _, location_evidence = assess_us_location(" ".join([location, *evidence]))
        if not is_us:
            continue

        company = job_summary.company_name if company_match else _extract_company(combined_text)
        candidate = ContactCandidate(
            full_name=full_name,
            title=role,
            location=location or "US-based (snippet-derived)",
            company=company or job_summary.company_name,
            profile_url=url,
            public_email=public_email,
            source_urls=unique_preserve_order([url]),
            evidence=unique_preserve_order(evidence + location_evidence),
            is_us_based=True,
        )
        candidates.append(candidate)

    recruiter_first = [item for item in candidates if is_recruiter_like_title(item.title)]
    others = [item for item in candidates if item not in recruiter_first]
    return recruiter_first + others


def _should_fetch_page(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if any(domain in host for domain in TARGET_DOMAINS):
        return False
    return host.startswith("www.") or "." in host


def _extract_name(title: str, snippet: str) -> str | None:
    segments = re.split(r"\s+\||\s+-\s+", title)
    for segment in segments:
        cleaned = normalize_whitespace(segment)
        if _looks_like_person_name(cleaned):
            return cleaned
    for match in re.findall(r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,2}", f"{title} {snippet}"):
        if _looks_like_person_name(match):
            return match
    return None


def _extract_title(title: str, snippet: str) -> str | None:
    text = f"{title} {snippet}"
    patterns = [
        r"(Senior Recruiter)",
        r"(Technical Recruiter)",
        r"(Talent Acquisition Partner)",
        r"(Talent Acquisition Manager)",
        r"(University Recruiter)",
        r"(Campus Recruiter)",
        r"(Recruiter)",
        r"(Technical Sourcer)",
        r"(Talent Sourcer)",
        r"(Sourcer)",
        r"(Hiring Manager)",
        r"(Engineering Manager)",
        r"(Director of [A-Za-z ]+)",
        r"(Head of [A-Za-z ]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_location(text: str) -> str:
    city_state = re.search(r"\b([A-Z][A-Za-z.\- ]+,\s*[A-Z]{2})\b", text)
    if city_state:
        return city_state.group(1)
    country = re.search(r"\b(United States|USA|US)\b", text, flags=re.IGNORECASE)
    if country:
        return country.group(1)
    return ""


def _extract_company(text: str) -> str:
    match = re.search(r"\b(?:at|with)\s+([A-Z][A-Za-z0-9&.\- ]{1,40})", text)
    return normalize_whitespace(match.group(1)) if match else ""


def _load_mock_results(company_name: str) -> list[dict[str, str]]:
    rows = json.loads(MOCK_FIXTURE_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, str]] = []
    for block in rows:
        for result in block.get("results", []):
            mutated = dict(result)
            mutated["title"] = mutated["title"].replace("Acme", company_name)
            mutated["snippet"] = mutated["snippet"].replace("Acme", company_name)
            results.append(mutated)
    return results


def _looks_like_person_name(value: str) -> bool:
    if not re.fullmatch(r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,2}", value):
        return False
    banned_terms = {"Recruiter", "Sourcer", "Talent", "Acquisition", "Manager", "Director", "Head", "LinkedIn"}
    return not any(term in value.split() for term in banned_terms)
