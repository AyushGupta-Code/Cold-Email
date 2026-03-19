from __future__ import annotations

from collections import Counter
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.api import (
    ContactCandidate,
    ContactEvidence,
    ContactSearchDebug,
    ContactSearchResponse,
    JobSummary,
    ProfilePictureEvidence,
    ResumeSummary,
)
from app.services.contact_llm import expand_queries_with_ollama, extract_candidates_with_ollama
from app.services.contact_ranker import company_match_score, is_recruiter_like_title, rank_contacts, title_bucket
from app.services.persistence import cache_artifact, cache_search_results, get_cached_artifact, get_cached_search
from app.services.us_filter import assess_us_location
from app.utils.http import create_session, normalize_result_url, request_with_retry
from app.utils.text import extract_email_addresses, normalize_company_name, normalize_whitespace, stable_cache_key, truncate_text, unique_preserve_order

MOCK_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "sample_data" / "mock_search_results.json"

HEURISTIC_QUERY_PATTERNS = [
    "{company} recruiter united states linkedin",
    "{company} technical recruiter united states linkedin",
    "{company} talent acquisition usa",
    "{company} talent acquisition partner united states",
    "{company} talent acquisition advisor usa",
    "{company} sourcer us",
    "{company} university recruiter us",
    "{company} campus recruiter united states",
    "{company} campus recruiting united states",
    "{company} university relations recruiter united states",
    "{company} recruiting manager united states",
    "{company} hiring manager {position} united states",
    "site:linkedin.com/in {company} recruiter us",
    "site:linkedin.com/in {company} talent acquisition united states",
    "site:linkedin.com/in {company} technical recruiter usa",
    "site:linkedin.com/in {company} university recruiter united states",
    "site:linkedin.com/in {company} campus recruiter united states",
    "site:linkedin.com/in {company} sourcer united states",
    "{company} recruiting team united states",
    "{company} careers recruiting team us",
    "{company} people team recruiting united states",
    "{company} hiring team {position} united states",
    "{company} staffing {position} united states",
    "{company} software hiring manager united states",
]
PROFILE_TITLE_TERMS = [
    "recruiter",
    "technical recruiter",
    "senior recruiter",
    "lead recruiter",
    "recruiting manager",
    "talent acquisition",
    "talent acquisition partner",
    "talent acquisition recruiter",
    "talent acquisition advisor",
    "technical sourcer",
    "talent sourcer",
    "sourcer",
    "campus recruiter",
    "campus recruiting",
    "university recruiter",
    "university relations recruiter",
    "staffing recruiter",
]
COMPANY_PAGE_TERMS = [
    "recruiting team",
    "talent acquisition team",
    "people team recruiting",
    "careers recruiting",
    "staffing team",
    "campus recruiting",
    "university recruiting",
]
US_LOCATION_QUERY_TERMS = [
    "United States",
    "Remote United States",
    "New York, NY",
    "Seattle, WA",
    "Austin, TX",
    "San Francisco, CA",
    "Chicago, IL",
    "Boston, MA",
    "Atlanta, GA",
    "Dallas, TX",
    "Washington, DC",
]
POSITION_FAMILY_TERMS = {
    "engineer": ["software engineering", "engineering", "platform engineering", "backend engineering"],
    "developer": ["software engineering", "engineering", "application development"],
    "data": ["data engineering", "analytics", "data platform"],
    "product": ["product", "product engineering"],
    "design": ["design", "product design"],
    "security": ["security engineering", "security"],
    "devops": ["platform engineering", "devops", "site reliability"],
}

TITLE_PATTERNS = [
    r"(Technical Recruiter)",
    r"(Senior Recruiter)",
    r"(Lead Recruiter)",
    r"(Recruiting Manager)",
    r"(Recruiting Lead)",
    r"(Recruiter)",
    r"(Talent Acquisition Partner)",
    r"(Talent Acquisition Manager)",
    r"(Talent Acquisition Specialist)",
    r"(Talent Acquisition Advisor)",
    r"(Talent Acquisition Recruiter)",
    r"(University Recruiter)",
    r"(University Relations Recruiter)",
    r"(Campus Recruiter)",
    r"(Campus Recruiting Manager)",
    r"(Campus Recruiting)",
    r"(Technical Sourcer)",
    r"(Talent Sourcer)",
    r"(Sourcing Recruiter)",
    r"(Sourcer)",
    r"(Staffing Recruiter)",
    r"(Staffing Manager)",
    r"(Hiring Manager)",
    r"(Engineering Manager)",
    r"(Director of [A-Za-z &/-]+)",
    r"(Head of [A-Za-z &/-]+)",
]

SEARCH_KEYWORDS = ("recruit", "talent", "sourc", "hiring", "staffing", "people")
PERSON_PAGE_HINTS = ("/in/", "/people", "/team", "/leadership", "/about", "/company")
PROFILE_PICTURE_NEGATIVE_HINTS = (
    "logo",
    "icon",
    "sprite",
    "banner",
    "placeholder",
    "default",
    "favicon",
    "wordmark",
    "brandmark",
    "masthead",
    "hero",
    "loader",
    "blank",
    "anonymous",
    "no-photo",
    "noimage",
    "site-logo",
)
PROFILE_PICTURE_POSITIVE_HINTS = (
    "headshot",
    "portrait",
    "profile photo",
    "profile picture",
    "photo",
    "speaker",
    "team member",
    "staff photo",
    "employee photo",
)
PROFILE_PICTURE_ATTRS = ("src", "data-src", "data-lazy-src", "data-original", "data-image")
PROFILE_PICTURE_THRESHOLD = 0.62
PROFILE_PICTURE_MIN_DIMENSION = 48
PROFILE_PICTURE_MAX_ASPECT_RATIO = 2.2


class SearchResultItem(BaseModel):
    title: str
    snippet: str
    url: str
    query_provenance: list[str] = Field(default_factory=list)
    search_source: str = ""


class FetchedPage(BaseModel):
    url: str
    text: str = ""
    html: str = ""
    fetch_method: str = "unavailable"
    error: str | None = None


class ExtractedContact(BaseModel):
    name: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    profile_url: str | None = None
    public_email: str | None = None
    evidence: list[ContactEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DiscoveredProfileImage(BaseModel):
    image_url: str
    source_url: str
    discovery_method: str
    context_text: str = ""
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None


def _emit_live_progress(settings: Settings, message: str) -> None:
    if not settings.discovery_log_progress:
        return
    print(f"[contact-search] {message}", file=sys.stderr, flush=True)


def _format_reason_counts(counts: Counter[str]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{reason}={count}" for reason, count in counts.most_common())


def discover_contacts(
    job_summary: JobSummary,
    resume_summary: ResumeSummary,
    db: Session,
    settings: Settings,
) -> ContactSearchResponse:
    warnings: list[str] = []
    debug = ContactSearchDebug()
    if settings.discovery_linkedin_only:
        _emit_live_progress(settings, "LinkedIn-only discovery mode is enabled.")

    heuristic_queries = _build_heuristic_queries(job_summary, settings.discovery_query_target_count)
    queries = heuristic_queries
    debug.heuristic_queries_generated = heuristic_queries
    llm_queries, llm_query_warnings, llm_query_used = expand_queries_with_ollama(job_summary, resume_summary, db, settings)
    debug.llm_queries_generated = llm_queries
    if llm_query_warnings:
        warnings.extend(llm_query_warnings)
    if llm_queries:
        queries = _combine_queries(heuristic_queries, llm_queries, settings.discovery_query_target_count)
    else:
        queries = heuristic_queries[: max(settings.discovery_query_target_count, 24)]
    debug.queries_generated = queries
    _emit_live_progress(settings, f"Starting discovery for {job_summary.company_name} / {job_summary.position}")
    if llm_queries:
        _emit_live_progress(settings, f"LLM generated {len(llm_queries)} query expansions:")
        for index, query in enumerate(llm_queries, start=1):
            _emit_live_progress(settings, f"  [llm {index:02d}] {query}")
    else:
        _emit_live_progress(settings, "LLM generated 0 query expansions; using heuristic query plan.")
    _emit_live_progress(settings, f"Running {len(queries)} combined search queries:")
    for index, query in enumerate(queries, start=1):
        _emit_live_progress(settings, f"  [query {index:02d}] {query}")

    raw_results: list[dict[str, Any]] = []
    mode = settings.discovery_mode.lower()
    if mode not in {"live", "fallback", "mock"}:
        warnings.append(f"Unknown discovery mode '{settings.discovery_mode}', defaulting to live.")
        mode = "live"

    if mode != "mock":
        raw_results, retrieval_warnings = _retrieve_public_results(queries, db, settings)
        warnings.extend(retrieval_warnings)

    if mode == "mock" or (mode == "fallback" and not raw_results):
        raw_results = _load_mock_results(job_summary.company_name)
        warnings.append("Using mock discovery data. Switch DISCOVERY_MODE=live for real public web discovery.")

    search_results = _prioritize_search_results(_aggregate_search_results(raw_results), job_summary.company_name)
    if settings.discovery_linkedin_only:
        prefilter_count = len(search_results)
        search_results = [result for result in search_results if _is_linkedin_profile_url(result.url)]
        removed = prefilter_count - len(search_results)
        if removed:
            warnings.append(f"Filtered out {removed} non-LinkedIn search results before extraction.")
        _emit_live_progress(
            settings,
            f"Aggregated {prefilter_count} unique search results; kept {len(search_results)} LinkedIn /in profiles and filtered out {removed} non-LinkedIn results.",
        )
    debug.urls_considered = len(search_results)
    if not search_results:
        warnings.append("Public search returned no usable results. Check search connectivity or clear stale cache entries.")

    fetched_pages, fetch_warnings = _fetch_promising_pages(search_results, db, settings)
    warnings.extend(fetch_warnings)
    fetched_page_urls = {page.url for page in fetched_pages}
    debug.pages_fetched = len([page for page in fetched_pages if page.text])

    source_documents: dict[tuple[str, str], str] = {}
    extracted_candidates: list[ExtractedContact] = []
    llm_extraction_used = False

    for result in search_results:
        source_text = _search_result_text(result)
        source_documents[(result.url, "search_snippet")] = source_text
        candidates, candidate_warnings, used_llm = _extract_from_source(
            source_url=result.url,
            source_type="search_snippet",
            source_text=source_text,
            title=result.title,
            job_summary=job_summary,
            db=db,
            settings=settings,
        )
        llm_extraction_used = llm_extraction_used or used_llm
        warnings.extend(candidate_warnings)
        extracted_candidates.extend(candidates)

    page_candidates, page_candidate_warnings, page_llm_used = _extract_candidates_from_pages(
        fetched_pages,
        source_documents,
        job_summary,
        db,
        settings,
    )
    llm_extraction_used = llm_extraction_used or page_llm_used
    warnings.extend(page_candidate_warnings)
    extracted_candidates.extend(page_candidates)

    debug.candidates_extracted = len(extracted_candidates)
    _emit_live_progress(
        settings,
        f"Extracted {len(extracted_candidates)} candidate mentions from {len(search_results)} search results and {debug.pages_fetched} fetched pages.",
    )
    if search_results and not extracted_candidates:
        warnings.append("Search results were found, but none contained extractable recruiter contacts with usable evidence.")

    if not llm_query_used or not llm_extraction_used:
        warnings.append(
            "LLM-assisted query expansion or extraction was partially unavailable; heuristic retrieval was used where needed."
        )

    merged_candidates = _merge_extracted_candidates(extracted_candidates, job_summary.company_name)
    _emit_live_progress(
        settings,
        f"Merged extracted mentions into {len(merged_candidates)} distinct candidate identities before validation.",
    )
    deduped, validation_rejections = _finalize_candidates(merged_candidates, job_summary, source_documents, settings)
    _emit_live_progress(
        settings,
        f"Validation rejections before image checks: {_format_reason_counts(validation_rejections)}",
    )
    deduped, picture_warnings, fetched_pages = _apply_profile_picture_filter(deduped, fetched_pages, db, settings)
    warnings.extend(picture_warnings)
    fetched_page_urls = {page.url for page in fetched_pages}
    debug.pages_fetched = len({page.url for page in fetched_pages if page.text or page.html})

    if len(deduped) < settings.discovery_max_contacts:
        additional_pages, additional_fetch_warnings = _fetch_promising_pages(
            search_results,
            db,
            settings,
            already_fetched=fetched_page_urls,
            page_limit=max(settings.discovery_max_pages_to_fetch * 2, settings.discovery_max_contacts * 4),
            aggressive=True,
        )
        warnings.extend(additional_fetch_warnings)
        if additional_pages:
            warnings.append("Expanded public-page fetch because the first pass found too few validated contacts.")
            fetched_pages.extend(additional_pages)
            fetched_page_urls.update(page.url for page in additional_pages)
            debug.pages_fetched = len({page.url for page in fetched_pages if page.text})
            page_candidates, page_candidate_warnings, page_llm_used = _extract_candidates_from_pages(
                additional_pages,
                source_documents,
                job_summary,
                db,
                settings,
            )
            llm_extraction_used = llm_extraction_used or page_llm_used
            warnings.extend(page_candidate_warnings)
            extracted_candidates.extend(page_candidates)
            debug.candidates_extracted = len(extracted_candidates)
            merged_candidates = _merge_extracted_candidates(extracted_candidates, job_summary.company_name)
            _emit_live_progress(
                settings,
                f"After expanded page fetch, merged mentions into {len(merged_candidates)} distinct candidate identities.",
            )
            deduped, validation_rejections = _finalize_candidates(merged_candidates, job_summary, source_documents, settings)
            _emit_live_progress(
                settings,
                f"Validation rejections before image checks: {_format_reason_counts(validation_rejections)}",
            )
            deduped, picture_warnings, fetched_pages = _apply_profile_picture_filter(deduped, fetched_pages, db, settings)
            warnings.extend(picture_warnings)
            fetched_page_urls = {page.url for page in fetched_pages}
            debug.pages_fetched = len({page.url for page in fetched_pages if page.text or page.html})

    debug.candidates_after_filtering = len(deduped)
    _emit_live_progress(settings, f"Validated {len(deduped)} contacts after evidence, location, and profile-picture filters.")

    ranked, ranking_warnings = rank_contacts(deduped, job_summary, resume_summary, settings, db, limit=settings.discovery_max_contacts)
    warnings.extend(ranking_warnings)

    ranked = [candidate for candidate in ranked if candidate.is_us_based][: settings.discovery_max_contacts]
    _emit_live_progress(settings, f"Returning {len(ranked)} ranked contacts.")
    if len(ranked) < settings.discovery_max_contacts:
        warnings.append(f"Only {len(ranked)} credible US-based contacts found")

    missing_email_count = sum(1 for candidate in ranked if not candidate.public_email)
    if ranked and missing_email_count:
        warnings.append(f"No public emails found for {missing_email_count} contacts")

    return ContactSearchResponse(
        contacts=ranked,
        warnings=unique_preserve_order(warnings),
        debug=debug,
    )


def deduplicate_contacts(candidates: list[ContactCandidate]) -> list[ContactCandidate]:
    deduped: dict[str, ContactCandidate] = {}
    for candidate in candidates:
        key = _candidate_dedup_key(candidate)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = candidate
            continue
        deduped[key] = _merge_contacts(existing, candidate)
    return list(deduped.values())


def extract_verified_public_email(*texts: str) -> str | None:
    matches: list[str] = []
    for text in texts:
        matches.extend(extract_email_addresses(text))
    return matches[0] if matches else None


def _build_heuristic_queries(job_summary: JobSummary, target_count: int) -> list[str]:
    keywords = " ".join(job_summary.important_skills[:3])
    max_count = max(target_count, 24)
    company = normalize_whitespace(job_summary.company_name)
    quoted_company = f"\"{company}\""
    position_terms = _position_search_terms(job_summary.position, job_summary.important_skills)
    manager_titles = _manager_search_terms(job_summary.position)
    seed_queries = [
        f"site:linkedin.com/in {quoted_company} \"recruiter\" \"Seattle, WA\"",
        f"site:linkedin.com/in {quoted_company} \"technical recruiter\" \"Austin, TX\"",
        f"site:linkedin.com/in {quoted_company} \"talent acquisition partner\" \"United States\"",
        f"site:linkedin.com/in {quoted_company} \"sourcer\" \"United States\"",
        f"site:linkedin.com/in {quoted_company} \"university recruiter\" \"United States\"",
        f"site:linkedin.com/in {quoted_company} \"campus recruiter\" \"United States\"",
        f"site:linkedin.com/in {quoted_company} \"hiring manager\" \"{job_summary.position}\"",
        f"site:linkedin.com/in {company} recruiter us",
    ]
    if any(term in normalize_whitespace(job_summary.position).casefold() for term in ("engineer", "developer", "software")):
        seed_queries.append(f"site:linkedin.com/in {quoted_company} \"engineering manager\" \"{job_summary.position}\"")

    base_queries = [
        pattern.format(company=job_summary.company_name, position=job_summary.position).strip()
        for pattern in HEURISTIC_QUERY_PATTERNS
    ]
    profile_queries: list[str] = []
    role_queries: list[str] = []
    manager_queries: list[str] = []
    keyword_queries: list[str] = []
    metro_queries: list[str] = []

    for title in PROFILE_TITLE_TERMS:
        profile_queries.extend(
            [
                f"site:linkedin.com/in {quoted_company} \"{title}\" \"United States\"",
                f"site:linkedin.com/in {quoted_company} \"{title}\" USA",
                f"{company} {title} united states linkedin",
            ]
        )

    for title in PROFILE_TITLE_TERMS[:10]:
        for role_term in position_terms[:4]:
            role_queries.extend(
                [
                f"site:linkedin.com/in {quoted_company} \"{title}\" \"{role_term}\"",
                    f"site:linkedin.com/in {quoted_company} \"{title}\" \"{role_term}\" USA",
                ]
            )

    for manager_title in manager_titles:
        manager_queries.extend(
            [
                f"site:linkedin.com/in {quoted_company} \"{manager_title}\" \"{job_summary.position}\"",
                f"site:linkedin.com/in {quoted_company} \"{manager_title}\" \"United States\"",
            ]
        )

    metro_titles = PROFILE_TITLE_TERMS[:8]
    metro_locations = US_LOCATION_QUERY_TERMS[:8]
    for location in metro_locations:
        for title in metro_titles[:4]:
            metro_queries.extend(
                [
                    f"site:linkedin.com/in {quoted_company} \"{title}\" \"{location}\"",
                    f"site:linkedin.com/in {quoted_company} \"{title}\" \"{location}\" recruiter",
                ]
            )

    if keywords:
        keyword_queries.extend(
            [
                f"site:linkedin.com/in {company} hiring manager {job_summary.position} us",
                f"site:linkedin.com/in {company} recruiter {job_summary.position} united states",
                f"site:linkedin.com/in {quoted_company} \"technical recruiter\" {keywords}",
                f"site:linkedin.com/in {quoted_company} \"technical sourcer\" {keywords} \"United States\"",
            ]
        )
    blended_queries = _blend_query_buckets(
        [base_queries, profile_queries, role_queries, manager_queries, keyword_queries, metro_queries],
        max_count * 3,
    )
    return _restrict_to_linkedin_queries(seed_queries + blended_queries, max_count)


def _combine_queries(heuristic_queries: list[str], llm_queries: list[str], target_count: int) -> list[str]:
    blended: list[str] = []
    heuristic = unique_preserve_order(heuristic_queries)
    llm = unique_preserve_order(llm_queries)
    max_count = max(target_count, 24)

    seed_count = min(max_count // 2, len(heuristic))
    blended.extend(heuristic[:seed_count])

    for index in range(max(len(llm), len(heuristic[seed_count:]))):
        if index < len(llm):
            blended.append(llm[index])
        heuristic_index = seed_count + index
        if heuristic_index < len(heuristic):
            blended.append(heuristic[heuristic_index])

    return _restrict_to_linkedin_queries(blended, max_count)


def _restrict_to_linkedin_queries(queries: list[str], limit: int) -> list[str]:
    linkedin_queries: list[str] = []
    for query in queries:
        normalized = normalize_whitespace(query)
        if not normalized:
            continue
        if "site:linkedin.com/in" not in normalized.casefold():
            normalized = f"site:linkedin.com/in {normalized}"
        linkedin_queries.append(normalize_whitespace(normalized))
    return unique_preserve_order(linkedin_queries)[:limit]


def _company_domain_hint(company_name: str) -> str | None:
    normalized = normalize_company_name(company_name).casefold()
    slug = re.sub(r"[^a-z0-9]+", "", normalized)
    if len(slug) < 4:
        return None
    return f"{slug}.com"


def _position_search_terms(position: str, important_skills: list[str]) -> list[str]:
    normalized = normalize_whitespace(position)
    lowered = normalized.casefold()
    terms = [normalized]
    for key, variants in POSITION_FAMILY_TERMS.items():
        if key in lowered:
            terms.extend(variants)
    terms.extend(skill for skill in important_skills[:3] if len(skill) > 2)
    return unique_preserve_order(terms)


def _manager_search_terms(position: str) -> list[str]:
    lowered = normalize_whitespace(position).casefold()
    terms = ["hiring manager"]
    if "engineer" in lowered or "developer" in lowered or "software" in lowered:
        terms.extend(["engineering manager", "software engineering manager", "director of engineering", "head of engineering"])
    elif "data" in lowered:
        terms.extend(["data engineering manager", "director of data engineering"])
    elif "product" in lowered:
        terms.extend(["product manager", "director of product"])
    elif "design" in lowered:
        terms.extend(["design manager", "head of design"])
    else:
        terms.extend(["team manager", "director", "head of team"])
    return unique_preserve_order(terms)


def _blend_query_buckets(buckets: list[list[str]], limit: int) -> list[str]:
    cleaned_buckets = [unique_preserve_order(bucket) for bucket in buckets if bucket]
    blended: list[str] = []
    max_bucket_length = max((len(bucket) for bucket in cleaned_buckets), default=0)
    for index in range(max_bucket_length):
        for bucket in cleaned_buckets:
            if index < len(bucket):
                blended.append(bucket[index])
    return unique_preserve_order(blended)[:limit]


def _retrieve_public_results(
    queries: list[str],
    db: Session,
    settings: Settings,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    unique_urls: set[str] = set()
    disabled_providers: dict[str, str] = {}
    target_url_count = max(settings.discovery_max_contacts * 10, settings.discovery_max_results_per_query * 4)
    for query in queries:
        query_results: list[dict[str, Any]] = []
        query_warnings: list[str] = []
        for provider in _provider_sequence(settings):
            if provider in disabled_providers:
                continue
            _emit_live_progress(settings, f"Searching via {provider}: {query}")
            if provider == "searxng":
                results, search_warnings = _search_searxng(query, db, settings)
            elif provider == "duckduckgo_html":
                results, search_warnings = _search_duckduckgo(query, db, settings)
            elif provider == "yahoo_html":
                results, search_warnings = _search_yahoo(query, db, settings)
            elif provider == "mojeek_html":
                results, search_warnings = _search_mojeek(query, db, settings)
            else:
                results, search_warnings = _search_bing(query, db, settings)
            linkedin_profile_results = sum(
                1 for row in results if _is_linkedin_profile_url(str(row.get("url", "")))
            )
            _emit_live_progress(
                settings,
                f"{provider} returned {len(results)} results ({linkedin_profile_results} LinkedIn /in profiles) for: {query}",
            )
            blocked_warning = _provider_block_warning(search_warnings)
            if blocked_warning:
                disabled_providers[provider] = blocked_warning
                summary = (
                    f"{_provider_label(provider)} is blocking automated HTML queries; "
                    f"disabled it for the rest of this run."
                )
                warnings.append(summary)
                _emit_live_progress(settings, summary)
            else:
                query_warnings.extend(search_warnings)
            query_results = _merge_query_results(query_results, results)
            if len(query_results) >= settings.discovery_max_results_per_query:
                break
        merged_linkedin_profiles = sum(
            1 for row in query_results if _is_linkedin_profile_url(str(row.get("url", "")))
        )
        _emit_live_progress(
            settings,
            f"Combined providers kept {len(query_results)} unique results ({merged_linkedin_profiles} LinkedIn /in profiles) for: {query}",
        )
        if not query_results:
            warnings.extend(unique_preserve_order(query_warnings))
        selected = query_results[: settings.discovery_max_results_per_query]
        rows.extend(selected)
        unique_urls.update(_normalize_profile_url(str(row.get("url", ""))) for row in selected if row.get("url"))
        if len({url for url in unique_urls if url}) >= target_url_count:
            break
        time.sleep(settings.discovery_request_delay_ms / 1000.0)
    return rows, warnings


def _provider_sequence(settings: Settings) -> list[str]:
    if settings.searxng_base_url.strip():
        return ["searxng", "duckduckgo_html", "bing_html", "yahoo_html", "mojeek_html"]
    return ["duckduckgo_html", "bing_html", "yahoo_html", "mojeek_html"]


def _provider_label(provider: str) -> str:
    labels = {
        "searxng": "SearxNG",
        "duckduckgo_html": "DuckDuckGo",
        "bing_html": "Bing",
        "yahoo_html": "Yahoo",
        "mojeek_html": "Mojeek",
    }
    return labels.get(provider, provider)


def _provider_block_warning(warnings: list[str]) -> str | None:
    for warning in warnings:
        lowered = warning.casefold()
        if any(token in lowered for token in ("403", "429", "forbidden", "too many requests", "captcha", "rate limit")):
            return warning
    return None


def _merge_query_results(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in left + right:
        url = _normalize_profile_url(str(row.get("url", "")))
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append({**row, "url": url})
    return merged


def _search_searxng(query: str, db: Session, settings: Settings) -> tuple[list[dict[str, Any]], list[str]]:
    cached = get_cached_search(db, "searxng", query)
    if cached is not None:
        return cached, []

    warnings: list[str] = []
    session = create_session()
    try:
        response = request_with_retry(
            session,
            "GET",
            f"{settings.searxng_base_url.rstrip('/')}/search",
            params={"q": query, "format": "json", "language": "en-US"},
            delay_ms=settings.discovery_request_delay_ms,
        )
        payload = response.json()
        results: list[dict[str, Any]] = []
        for item in payload.get("results", [])[: settings.discovery_max_results_per_query]:
            url = normalize_result_url(str(item.get("url", "")))
            if not url:
                continue
            results.append(
                {
                    "title": normalize_whitespace(str(item.get("title", ""))),
                    "snippet": normalize_whitespace(str(item.get("content", ""))),
                    "url": url,
                    "query": query,
                    "search_source": "searxng",
                }
            )
        cache_search_results(db, "searxng", query, results)
        return results, warnings
    except Exception as exc:
        warnings.append(f"SearxNG query failed for '{query}': {exc}")
        return [], warnings


def _search_duckduckgo(query: str, db: Session, settings: Settings) -> tuple[list[dict[str, Any]], list[str]]:
    cached = get_cached_search(db, "duckduckgo_html", query)
    if cached is not None:
        return cached, []

    warnings: list[str] = []
    session = create_session()
    try:
        response = request_with_retry(
            session,
            "POST",
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            delay_ms=settings.discovery_request_delay_ms,
        )
        results = _parse_duckduckgo_results(response.text, query, settings.discovery_max_results_per_query)
        cache_search_results(db, "duckduckgo_html", query, results)
        return results, warnings
    except Exception as exc:
        warnings.append(f"Search query failed for '{query}': {exc}")
        return [], warnings


def _search_bing(query: str, db: Session, settings: Settings) -> tuple[list[dict[str, Any]], list[str]]:
    cached = get_cached_search(db, "bing_html", query)
    if cached is not None:
        return cached, []

    warnings: list[str] = []
    session = create_session()
    try:
        response = request_with_retry(
            session,
            "GET",
            "https://www.bing.com/search",
            params={"q": query, "setlang": "en-US"},
            delay_ms=settings.discovery_request_delay_ms,
        )
        results = _parse_bing_results(response.text, query, settings.discovery_max_results_per_query)
        cache_search_results(db, "bing_html", query, results)
        return results, warnings
    except Exception as exc:
        warnings.append(f"Bing fallback query failed for '{query}': {exc}")
        return [], warnings


def _search_yahoo(query: str, db: Session, settings: Settings) -> tuple[list[dict[str, Any]], list[str]]:
    cached = get_cached_search(db, "yahoo_html", query)
    if cached is not None:
        return cached, []

    warnings: list[str] = []
    session = create_session()
    try:
        response = request_with_retry(
            session,
            "GET",
            "https://search.yahoo.com/search",
            params={"p": query, "ei": "UTF-8"},
            delay_ms=settings.discovery_request_delay_ms,
        )
        results = _parse_yahoo_results(response.text, query, settings.discovery_max_results_per_query)
        cache_search_results(db, "yahoo_html", query, results)
        return results, warnings
    except Exception as exc:
        warnings.append(f"Yahoo query failed for '{query}': {exc}")
        return [], warnings


def _search_mojeek(query: str, db: Session, settings: Settings) -> tuple[list[dict[str, Any]], list[str]]:
    cached = get_cached_search(db, "mojeek_html", query)
    if cached is not None:
        return cached, []

    warnings: list[str] = []
    session = create_session()
    try:
        response = request_with_retry(
            session,
            "GET",
            "https://www.mojeek.com/search",
            params={"q": query},
            delay_ms=settings.discovery_request_delay_ms,
        )
        results = _parse_mojeek_results(response.text, query, settings.discovery_max_results_per_query)
        cache_search_results(db, "mojeek_html", query, results)
        return results, warnings
    except Exception as exc:
        warnings.append(f"Mojeek query failed for '{query}': {exc}")
        return [], warnings


def _parse_duckduckgo_results(html: str, query: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for result in soup.select(".result, .results_links, .web-result"):
        link = result.select_one(".result__a, .result__title a, a.result-link")
        snippet = result.select_one(".result__snippet, .result__extras__url + a, .result__body")
        if not link:
            continue
        url = normalize_result_url(link.get("href", ""))
        if not url:
            continue
        rows.append(
            {
                "title": normalize_whitespace(link.get_text(" ", strip=True)),
                "snippet": normalize_whitespace(snippet.get_text(" ", strip=True) if snippet else ""),
                "url": url,
                "query": query,
                "search_source": "duckduckgo_html",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _parse_bing_results(html: str, query: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for result in soup.select("li.b_algo"):
        link = result.select_one("h2 a, a")
        snippet = result.select_one(".b_caption p, p")
        if not link:
            continue
        url = normalize_result_url(link.get("href", ""))
        if not url:
            continue
        rows.append(
            {
                "title": normalize_whitespace(link.get_text(" ", strip=True)),
                "snippet": normalize_whitespace(snippet.get_text(" ", strip=True) if snippet else ""),
                "url": url,
                "query": query,
                "search_source": "bing_html",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _parse_yahoo_results(html: str, query: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for result in soup.select("div.algo, div.algo-sr, li div.dd.algo, ol.searchCenterMiddle li"):
        link = result.select_one("h3.title a, h3 a, a")
        snippet = result.select_one(".compText, .compText p, p")
        if not link:
            continue
        url = normalize_result_url(link.get("href", ""))
        if not url:
            continue
        rows.append(
            {
                "title": normalize_whitespace(link.get_text(" ", strip=True)),
                "snippet": normalize_whitespace(snippet.get_text(" ", strip=True) if snippet else ""),
                "url": url,
                "query": query,
                "search_source": "yahoo_html",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _parse_mojeek_results(html: str, query: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, Any]] = []
    for result in soup.select("div.result, li.result, li[class*='result'], .results-standard li"):
        link = result.select_one("h2 a, .title a, a.title, a[href]")
        snippet = result.select_one(".result-desc, .excerpt, .description, p")
        if not link:
            continue
        url = normalize_result_url(link.get("href", ""))
        if not url:
            continue
        rows.append(
            {
                "title": normalize_whitespace(link.get_text(" ", strip=True)),
                "snippet": normalize_whitespace(snippet.get_text(" ", strip=True) if snippet else ""),
                "url": url,
                "query": query,
                "search_source": "mojeek_html",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _aggregate_search_results(raw_results: list[dict[str, Any]]) -> list[SearchResultItem]:
    aggregated: dict[str, SearchResultItem] = {}
    for row in raw_results:
        url = _normalize_profile_url(str(row.get("url", "")))
        title = normalize_whitespace(str(row.get("title", "")))
        snippet = normalize_whitespace(str(row.get("snippet", "")))
        query = normalize_whitespace(str(row.get("query", "")))
        if not url or not title:
            continue
        existing = aggregated.get(url)
        if existing is None:
            aggregated[url] = SearchResultItem(
                title=title,
                snippet=snippet,
                url=url,
                query_provenance=[query] if query else [],
                search_source=normalize_whitespace(str(row.get("search_source", ""))),
            )
            continue
        if len(title) > len(existing.title):
            existing.title = title
        if len(snippet) > len(existing.snippet):
            existing.snippet = snippet
        existing.query_provenance = unique_preserve_order(existing.query_provenance + ([query] if query else []))
    return list(aggregated.values())


def _prioritize_search_results(results: list[SearchResultItem], target_company: str) -> list[SearchResultItem]:
    return sorted(
        results,
        key=lambda result: _search_result_priority(result, target_company),
        reverse=True,
    )


def _search_result_priority(result: SearchResultItem, target_company: str) -> tuple[int, int, int, int]:
    combined = normalize_whitespace(" ".join([result.title, result.snippet, result.url]))
    host = urlparse(result.url).netloc.casefold()
    title_score = int(title_bucket(combined)[1] * 100)
    company_score = int(company_match_score(combined, target_company, combined) * 100)
    recruiter_signal = 1 if any(keyword in combined.casefold() for keyword in SEARCH_KEYWORDS) else 0
    public_profile_signal = 1 if _is_linkedin_profile_url(result.url) or any(marker in result.url.casefold() for marker in PERSON_PAGE_HINTS) else 0
    return public_profile_signal, recruiter_signal, title_score, company_score


def _fetch_promising_pages(
    results: list[SearchResultItem],
    db: Session,
    settings: Settings,
    *,
    already_fetched: set[str] | None = None,
    page_limit: int | None = None,
    aggressive: bool = False,
) -> tuple[list[FetchedPage], list[str]]:
    warnings: list[str] = []
    pages: list[FetchedPage] = []
    skipped_urls = already_fetched or set()
    max_pages = page_limit or settings.discovery_max_pages_to_fetch
    for result in results:
        if len(pages) >= max_pages:
            break
        if result.url in skipped_urls:
            continue
        if not _is_promising_result(result, aggressive=aggressive):
            continue
        page = _fetch_page(result.url, db, settings)
        if page.error:
            warnings.append(f"Page fetch failed for {result.url}: {page.error}")
        pages.append(page)
    return pages, warnings


def _fetch_page(url: str, db: Session, settings: Settings) -> FetchedPage:
    cache_key = stable_cache_key("public-page-fetch-v2", url, settings.discovery_use_playwright_fallback)
    cached = get_cached_artifact(db, "public_page_fetch", cache_key)
    if isinstance(cached, dict):
        return FetchedPage.model_validate(cached)

    session = create_session()
    html = ""
    fetch_method = "requests"
    error: str | None = None
    try:
        response = request_with_retry(session, "GET", url, timeout=12, delay_ms=settings.discovery_request_delay_ms)
        html = response.text
    except Exception as exc:
        error = str(exc)
        fetch_method = "requests"

    if not html and settings.discovery_use_playwright_fallback:
        try:  # pragma: no cover - Playwright availability depends on environment
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=20000)
                html = page.content()
                browser.close()
                fetch_method = "playwright"
                error = None
        except Exception as exc:  # pragma: no cover
            error = str(exc)

    compact_text = _compact_page_text(html, settings.discovery_max_extraction_chars)
    payload = FetchedPage(url=url, text=compact_text, html=html, fetch_method=fetch_method, error=error)
    cache_artifact(db, "public_page_fetch", cache_key, payload.model_dump())
    return payload


def _extract_from_source(
    *,
    source_url: str,
    source_type: str,
    source_text: str,
    title: str,
    job_summary: JobSummary,
    db: Session,
    settings: Settings,
) -> tuple[list[ExtractedContact], list[str], bool]:
    warnings: list[str] = []
    llm_candidates, llm_warnings, used_llm = extract_candidates_with_ollama(
        source_url=source_url,
        source_type=source_type,
        source_text=source_text,
        job_summary=job_summary,
        settings=settings,
        db=db,
    )
    warnings.extend(llm_warnings)

    raw_candidates = llm_candidates or _heuristic_extract_candidates(
        source_url=source_url,
        source_type=source_type,
        source_text=source_text,
        title=title,
        target_company=job_summary.company_name,
    )
    candidates = [_normalize_extracted_candidate(item, source_url, source_type, source_text, job_summary) for item in raw_candidates]
    return [candidate for candidate in candidates if candidate is not None], warnings, used_llm and bool(llm_candidates)


def _heuristic_extract_candidates(
    *,
    source_url: str,
    source_type: str,
    source_text: str,
    title: str,
    target_company: str,
) -> list[dict[str, Any]]:
    name = _extract_name(title, source_text)
    role = _extract_title(title, source_text)
    if not name or not role:
        return []

    company = _extract_supported_company(source_text, target_company, source_url)
    location = _extract_location(source_text)
    public_email = extract_verified_public_email(source_text)
    evidence = _build_supporting_evidence(
        source_url=source_url,
        source_type=source_type,
        source_text=source_text,
        terms=[name, role, company or target_company, location or "", public_email or ""],
    )
    return [
        {
            "name": name,
            "title": role,
            "company": company,
            "location": location,
            "profile_url": source_url,
            "public_email": public_email,
            "evidence": [item.model_dump() for item in evidence],
        }
    ]


def _normalize_extracted_candidate(
    payload: dict[str, Any],
    source_url: str,
    source_type: str,
    source_text: str,
    job_summary: JobSummary,
) -> ExtractedContact | None:
    evidence_items: list[ContactEvidence] = []
    for item in payload.get("evidence", []):
        try:
            evidence = ContactEvidence.model_validate(item)
        except Exception:
            continue
        quoted_text = normalize_whitespace(evidence.quoted_text)
        if not quoted_text:
            continue
        if not _quote_supported(quoted_text, source_text):
            continue
        evidence_items.append(
            ContactEvidence(
                source_url=evidence.source_url or source_url,
                source_type="page" if evidence.source_type == "page" else "search_snippet",
                quoted_text=truncate_text(quoted_text, 220),
            )
        )

    if not evidence_items:
        evidence_items = _build_supporting_evidence(
            source_url=source_url,
            source_type=source_type,
            source_text=source_text,
            terms=[
                normalize_whitespace(str(payload.get("name") or "")),
                normalize_whitespace(str(payload.get("title") or "")),
                normalize_whitespace(str(payload.get("company") or "")) or job_summary.company_name,
                normalize_whitespace(str(payload.get("location") or "")),
                normalize_whitespace(str(payload.get("public_email") or "")),
            ],
        )

    if not evidence_items:
        return None

    return ExtractedContact(
        name=_nullable_str(payload.get("name")),
        title=_nullable_str(payload.get("title")),
        company=_nullable_str(payload.get("company")),
        location=_nullable_str(payload.get("location")),
        profile_url=_nullable_str(payload.get("profile_url")) or source_url,
        public_email=_nullable_str(payload.get("public_email")),
        evidence=evidence_items,
    )


def _extract_candidates_from_pages(
    pages: list[FetchedPage],
    source_documents: dict[tuple[str, str], str],
    job_summary: JobSummary,
    db: Session,
    settings: Settings,
) -> tuple[list[ExtractedContact], list[str], bool]:
    warnings: list[str] = []
    extracted_candidates: list[ExtractedContact] = []
    used_llm = False
    for page in pages:
        if not page.text:
            continue
        source_documents[(page.url, "page")] = page.text
        candidates, candidate_warnings, candidate_used_llm = _extract_from_source(
            source_url=page.url,
            source_type="page",
            source_text=page.text,
            title="",
            job_summary=job_summary,
            db=db,
            settings=settings,
        )
        used_llm = used_llm or candidate_used_llm
        warnings.extend(candidate_warnings)
        extracted_candidates.extend(candidates)
    return extracted_candidates, warnings, used_llm


def _apply_profile_picture_filter(
    candidates: list[ContactCandidate],
    fetched_pages: list[FetchedPage],
    db: Session,
    settings: Settings,
) -> tuple[list[ContactCandidate], list[str], list[FetchedPage]]:
    if not candidates:
        return [], [], fetched_pages

    page_lookup = {page.url: page for page in fetched_pages}
    kept: list[ContactCandidate] = []
    rejection_counts: Counter[str] = Counter()

    for candidate in candidates:
        enriched, rejection_reason = _attach_profile_picture(candidate, page_lookup, db, settings)
        if enriched is None:
            if rejection_reason:
                rejection_counts[rejection_reason] += 1
            continue
        kept.append(enriched)

    warnings: list[str] = []
    filtered_out = sum(rejection_counts.values())
    if filtered_out:
        warnings.append(
            f"Filtered out {filtered_out} contacts without a credible public profile picture discovered from public evidence."
        )
        _emit_live_progress(
            settings,
            f"Profile picture filter rejected {filtered_out} contacts: {_format_reason_counts(rejection_counts)}",
        )
    else:
        _emit_live_progress(settings, "Profile picture filter rejected 0 contacts.")
    if candidates and not kept:
        warnings.append(
            "No contacts satisfied the public profile picture requirement; contacts without a public profile picture were filtered out."
        )

    return kept, warnings, list(page_lookup.values())


def _attach_profile_picture(
    candidate: ContactCandidate,
    page_lookup: dict[str, FetchedPage],
    db: Session,
    settings: Settings,
) -> tuple[ContactCandidate | None, str | None]:
    candidate_pages = _candidate_public_pages(candidate, page_lookup, db, settings)
    if not candidate_pages:
        return None, "no_public_profile_page"
    discovered_images: list[DiscoveredProfileImage] = []
    for page in candidate_pages:
        discovered_images.extend(_discover_profile_images_from_page(candidate, page))

    best = _select_best_profile_image(candidate, discovered_images)
    if best is None:
        return None, "no_credible_picture_found"

    confidence = _score_profile_image(candidate, best)
    if confidence < PROFILE_PICTURE_THRESHOLD:
        return None, "low_picture_confidence"

    evidence = [
        ProfilePictureEvidence(
            source_url=best.source_url,
            source_type="page",
            image_url=best.image_url,
            discovery_method=best.discovery_method,  # type: ignore[arg-type]
            context_text=truncate_text(best.context_text, 220),
            alt_text=best.alt_text,
        )
    ]
    return (
        candidate.model_copy(
            update={
                "profile_picture_url": best.image_url,
                "profile_picture_source_url": best.source_url,
                "profile_picture_confidence": round(confidence, 3),
                "profile_picture_evidence": evidence,
                "has_profile_picture": True,
            }
        ),
        None,
    )


def _candidate_public_pages(
    candidate: ContactCandidate,
    page_lookup: dict[str, FetchedPage],
    db: Session,
    settings: Settings,
) -> list[FetchedPage]:
    pages: list[FetchedPage] = []
    for url in unique_preserve_order([candidate.profile_url] + candidate.source_urls):
        page = _get_or_fetch_public_page(url, page_lookup, db, settings)
        if page is None or not page.html:
            continue
        pages.append(page)
    return pages


def _get_or_fetch_public_page(
    url: str,
    page_lookup: dict[str, FetchedPage],
    db: Session,
    settings: Settings,
) -> FetchedPage | None:
    normalized_url = _normalize_profile_url(url)
    if not normalized_url:
        return None

    existing = page_lookup.get(normalized_url)
    if existing is not None and existing.html:
        return existing

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    fetched = _fetch_page(normalized_url, db, settings)
    page_lookup[normalized_url] = fetched
    return fetched if fetched.html else None


def _discover_profile_images_from_page(candidate: ContactCandidate, page: FetchedPage) -> list[DiscoveredProfileImage]:
    if not page.html:
        return []

    soup = BeautifulSoup(page.html, "lxml")
    page_context = _page_identity_context(soup)
    discovered: list[DiscoveredProfileImage] = []

    for selector, method in (
        ('meta[property="og:image"]', "og_image"),
        ('meta[name="og:image"]', "og_image"),
        ('meta[property="twitter:image"]', "twitter_image"),
        ('meta[name="twitter:image"]', "twitter_image"),
    ):
        for tag in soup.select(selector):
            image_url = _normalize_asset_url(tag.get("content", ""), page.url)
            if not image_url:
                continue
            discovered.append(
                DiscoveredProfileImage(
                    image_url=image_url,
                    source_url=page.url,
                    discovery_method=method,
                    context_text=page_context,
                    alt_text=None,
                )
            )

    for item in _discover_profile_images_from_json_ld(candidate, soup, page.url):
        discovered.append(item)

    for tag in soup.find_all("img"):
        image_url = _image_url_from_tag(tag, page.url)
        if not image_url:
            continue
        width, height = _extract_image_dimensions(tag)
        alt_text = normalize_whitespace(" ".join([tag.get("alt", ""), tag.get("title", "")])) or None
        context_text = _image_context_text(tag, page_context)
        discovered.append(
            DiscoveredProfileImage(
                image_url=image_url,
                source_url=page.url,
                discovery_method="img_tag",
                context_text=context_text,
                alt_text=alt_text,
                width=width,
                height=height,
            )
        )

    deduped: dict[tuple[str, str], DiscoveredProfileImage] = {}
    for image in discovered:
        key = (image.image_url, image.source_url)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = image
            continue
        if len(image.context_text) > len(existing.context_text):
            deduped[key] = image
    return list(deduped.values())


def _discover_profile_images_from_json_ld(
    candidate: ContactCandidate,
    soup: BeautifulSoup,
    page_url: str,
) -> list[DiscoveredProfileImage]:
    discovered: list[DiscoveredProfileImage] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        for obj in _iter_json_ld_objects(payload):
            type_value = normalize_whitespace(str(obj.get("@type", ""))).casefold()
            name = normalize_whitespace(str(obj.get("name", "")))
            if "person" not in type_value and _name_association_score(candidate.full_name or candidate.name or "", name) < 1.0:
                continue
            context_text = normalize_whitespace(
                " ".join(
                    [
                        name,
                        str(obj.get("jobTitle", "") or ""),
                        _json_ld_org_name(obj.get("worksFor")),
                        str(obj.get("description", "") or ""),
                    ]
                )
            )
            for field_name in ("image", "photo"):
                for image_url in _json_ld_image_urls(obj.get(field_name), page_url):
                    discovered.append(
                        DiscoveredProfileImage(
                            image_url=image_url,
                            source_url=page_url,
                            discovery_method="json_ld",
                            context_text=context_text,
                            alt_text=name or None,
                        )
                    )
    return discovered


def _select_best_profile_image(
    candidate: ContactCandidate,
    images: list[DiscoveredProfileImage],
) -> DiscoveredProfileImage | None:
    scored = [(image, _score_profile_image(candidate, image)) for image in images]
    eligible = [(image, score) for image, score in scored if score >= PROFILE_PICTURE_THRESHOLD]
    if not eligible:
        return None
    eligible.sort(
        key=lambda item: (
            item[1],
            _name_association_score(candidate.full_name or candidate.name or "", _profile_image_text(item[0])),
            item[0].source_url == candidate.profile_url,
        ),
        reverse=True,
    )
    return eligible[0][0]


def _score_profile_image(candidate: ContactCandidate, image: DiscoveredProfileImage) -> float:
    url_lower = image.image_url.casefold()
    context_lower = _profile_image_text(image).casefold()

    if any(hint in url_lower or hint in context_lower for hint in PROFILE_PICTURE_NEGATIVE_HINTS):
        return 0.0
    if any(marker in url_lower for marker in ("data:image", "javascript:", "mailto:")):
        return 0.0

    width = image.width or 0
    height = image.height or 0
    if width and height:
        if min(width, height) < PROFILE_PICTURE_MIN_DIMENSION:
            return 0.0
        aspect_ratio = max(width / max(height, 1), height / max(width, 1))
        if aspect_ratio > PROFILE_PICTURE_MAX_ASPECT_RATIO:
            return 0.0

    name_score = _name_association_score(candidate.full_name or candidate.name or "", context_lower)
    url_name_score = _name_association_score(candidate.full_name or candidate.name or "", url_lower)
    title_score = _title_association_score(candidate.title, context_lower)
    person_hint = 1.0 if any(hint in context_lower for hint in PROFILE_PICTURE_POSITIVE_HINTS) else 0.0
    aspect_score = _profile_image_aspect_score(width, height)
    source_score = {
        "json_ld": 0.32,
        "img_tag": 0.24,
        "og_image": 0.18,
        "twitter_image": 0.16,
    }.get(image.discovery_method, 0.0)

    if image.discovery_method in {"og_image", "twitter_image"} and name_score < 0.75 and title_score < 0.4:
        return 0.0
    if image.discovery_method == "img_tag" and max(name_score, url_name_score) < 1.0 and person_hint == 0.0:
        return 0.0
    if image.image_url.casefold().endswith(".svg") and name_score < 1.0:
        return 0.0

    score = (
        source_score
        + min(name_score, 1.0) * 0.34
        + min(url_name_score, 1.0) * 0.12
        + min(title_score, 1.0) * 0.12
        + person_hint * 0.10
        + aspect_score * 0.12
        + (0.08 if image.source_url == candidate.profile_url else 0.0)
    )

    if any(marker in url_lower for marker in ("/assets/", "/static/", "/sprites/", "/icons/")) and name_score < 1.0:
        score -= 0.18

    return max(0.0, min(score, 1.0))


def _profile_image_text(image: DiscoveredProfileImage) -> str:
    return normalize_whitespace(" ".join([image.image_url, image.alt_text or "", image.context_text]))


def _page_identity_context(soup: BeautifulSoup) -> str:
    parts = [
        soup.title.get_text(" ", strip=True) if soup.title else "",
        *(tag.get("content", "") for tag in soup.select('meta[property="og:title"], meta[name="og:title"]')),
        *(tag.get("content", "") for tag in soup.select('meta[property="og:description"], meta[name="description"]')),
    ]
    return truncate_text(normalize_whitespace(" ".join(parts)), 320)


def _image_url_from_tag(tag: Any, page_url: str) -> str | None:
    for attribute in PROFILE_PICTURE_ATTRS:
        image_url = _normalize_asset_url(tag.get(attribute, ""), page_url)
        if image_url:
            return image_url
    srcset = normalize_whitespace(tag.get("srcset", "") or tag.get("data-srcset", ""))
    if not srcset:
        return None
    first_entry = srcset.split(",")[0].strip().split(" ")[0]
    return _normalize_asset_url(first_entry, page_url)


def _normalize_asset_url(url: str, base_url: str) -> str | None:
    normalized = normalize_whitespace(url)
    if not normalized:
        return None
    absolute = urljoin(base_url, normalized)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return urlunparse(parsed._replace(fragment=""))


def _extract_image_dimensions(tag: Any) -> tuple[int | None, int | None]:
    width = _parse_dimension_value(tag.get("width"))
    height = _parse_dimension_value(tag.get("height"))
    if width and height:
        return width, height
    width = _parse_dimension_value(tag.get("data-width"))
    height = _parse_dimension_value(tag.get("data-height"))
    return width, height


def _parse_dimension_value(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    parsed = int(match.group(0))
    return parsed if parsed > 0 else None


def _image_context_text(tag: Any, page_context: str) -> str:
    contexts: list[str] = []
    current = tag
    for _ in range(5):
        if current is None:
            break
        text = normalize_whitespace(current.get_text(" ", strip=True))
        if text:
            contexts.append(truncate_text(text, 320))
        current = getattr(current, "parent", None)

    combined = normalize_whitespace(" ".join(contexts[:2] + [page_context]))
    return truncate_text(combined, 320)


def _name_association_score(name: str, text: str) -> float:
    normalized_name = normalize_whitespace(name).casefold()
    normalized_text = normalize_whitespace(text).casefold()
    if not normalized_name or not normalized_text:
        return 0.0
    if normalized_name in normalized_text:
        return 1.0
    name_tokens = [token.casefold() for token in normalized_name.split() if len(token) > 1]
    if not name_tokens:
        return 0.0
    matched_tokens = sum(1 for token in name_tokens if token in normalized_text)
    return matched_tokens / len(name_tokens)


def _title_association_score(title: str, text: str) -> float:
    normalized_title = normalize_whitespace(title).casefold()
    normalized_text = normalize_whitespace(text).casefold()
    if not normalized_title or not normalized_text:
        return 0.0
    if normalized_title in normalized_text:
        return 1.0
    title_tokens = [token for token in normalized_title.split() if len(token) > 3]
    if not title_tokens:
        return 0.0
    matched_tokens = sum(1 for token in title_tokens if token in normalized_text)
    return matched_tokens / len(title_tokens)


def _profile_image_aspect_score(width: int, height: int) -> float:
    if not width or not height:
        return 0.05
    ratio = width / max(height, 1)
    if 0.75 <= ratio <= 1.4:
        return 1.0
    if 0.55 <= ratio < 0.75 or 1.4 < ratio <= 1.8:
        return 0.7
    return 0.0


def _iter_json_ld_objects(payload: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        objects.append(payload)
        for value in payload.values():
            objects.extend(_iter_json_ld_objects(value))
    elif isinstance(payload, list):
        for item in payload:
            objects.extend(_iter_json_ld_objects(item))
    return objects


def _json_ld_org_name(value: Any) -> str:
    if isinstance(value, dict):
        return normalize_whitespace(str(value.get("name", "")))
    if isinstance(value, list):
        parts = [_json_ld_org_name(item) for item in value]
        return normalize_whitespace(" ".join(part for part in parts if part))
    return normalize_whitespace(str(value or ""))


def _json_ld_image_urls(value: Any, page_url: str) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str):
        normalized = _normalize_asset_url(value, page_url)
        if normalized:
            urls.append(normalized)
    elif isinstance(value, dict):
        for key in ("url", "contentUrl"):
            normalized = _normalize_asset_url(str(value.get(key, "")), page_url)
            if normalized:
                urls.append(normalized)
        if not urls:
            urls.extend(_json_ld_image_urls(value.get("@id"), page_url))
    elif isinstance(value, list):
        for item in value:
            urls.extend(_json_ld_image_urls(item, page_url))
    return unique_preserve_order(urls)


def _merge_extracted_candidates(candidates: list[ExtractedContact], target_company: str) -> list[ExtractedContact]:
    merged: dict[str, ExtractedContact] = {}
    for candidate in candidates:
        key = _extracted_candidate_key(candidate, target_company)
        existing = merged.get(key)
        if existing is None:
            merged[key] = candidate
            continue
        merged[key] = _merge_extracted_contact(existing, candidate, target_company)
    return list(merged.values())


def _finalize_candidates(
    candidates: list[ExtractedContact],
    job_summary: JobSummary,
    source_documents: dict[tuple[str, str], str],
    settings: Settings,
) -> tuple[list[ContactCandidate], Counter[str]]:
    finalized_contacts: list[ContactCandidate] = []
    rejection_counts: Counter[str] = Counter()
    for candidate in candidates:
        finalized, rejection_reason = _finalize_candidate(candidate, job_summary, source_documents, settings)
        if finalized is not None:
            finalized_contacts.append(finalized)
            continue
        if rejection_reason:
            rejection_counts[rejection_reason] += 1
    return deduplicate_contacts(finalized_contacts), rejection_counts


def _finalize_candidate(
    candidate: ExtractedContact,
    job_summary: JobSummary,
    source_documents: dict[tuple[str, str], str],
    settings: Settings,
) -> tuple[ContactCandidate | None, str | None]:
    evidence = _validated_evidence(candidate.evidence, source_documents)
    if not evidence:
        return None, "no_valid_evidence"

    source_text = " ".join(
        source_documents.get((item.source_url, item.source_type), "")
        for item in evidence
    )

    name = candidate.name if _field_supported(candidate.name, source_text) else None
    title = candidate.title if _field_supported(candidate.title, source_text) else None
    company = candidate.company if _company_supported(candidate.company, source_text, job_summary.company_name) else None
    location = candidate.location if _field_supported(candidate.location, source_text) else None

    if not company:
        company = _extract_supported_company(source_text, job_summary.company_name, candidate.profile_url or "")
    if not location:
        location = _extract_location(source_text)

    profile_url = _normalize_profile_url(candidate.profile_url or evidence[0].source_url)
    if settings.discovery_linkedin_only and not _is_linkedin_profile_url(profile_url):
        return None, "not_linkedin_profile"
    public_email = None
    if candidate.public_email:
        explicit_email = extract_verified_public_email(source_text)
        if explicit_email and explicit_email.casefold() == candidate.public_email.casefold():
            public_email = explicit_email

    if not name or not title or not company or not location or not profile_url:
        return None, "missing_supported_identity_field"

    if company_match_score(company, job_summary.company_name, source_text) < 0.74:
        return None, "company_mismatch"
    if title_bucket(title)[1] < 0.68:
        return None, "non_recruiter_title"

    is_us, _, _ = assess_us_location(" ".join([location, source_text]))
    if not is_us:
        return None, "non_us_location"

    source_urls = unique_preserve_order([item.source_url for item in evidence])
    return (
        ContactCandidate(
            name=name,
            full_name=name,
            title=title,
            location=location,
            company=company,
            profile_url=profile_url,
            public_email=public_email,
            source_urls=source_urls,
            evidence=evidence,
            warnings=[],
            is_us_based=True,
        ),
        None,
    )


def _validated_evidence(
    evidence: list[ContactEvidence],
    source_documents: dict[tuple[str, str], str],
) -> list[ContactEvidence]:
    validated: list[ContactEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    for item in evidence:
        source_text = source_documents.get((item.source_url, item.source_type), "")
        if not source_text or not _quote_supported(item.quoted_text, source_text):
            continue
        key = (item.source_url, item.source_type, item.quoted_text.casefold())
        if key in seen:
            continue
        seen.add(key)
        validated.append(item)
    return validated


def _build_supporting_evidence(
    *,
    source_url: str,
    source_type: str,
    source_text: str,
    terms: list[str],
) -> list[ContactEvidence]:
    evidence: list[ContactEvidence] = []
    for term in terms:
        quote = _extract_quote(source_text, term)
        if not quote:
            continue
        evidence.append(
            ContactEvidence(
                source_url=source_url,
                source_type="page" if source_type == "page" else "search_snippet",
                quoted_text=quote,
            )
        )
    deduped: list[ContactEvidence] = []
    seen: set[str] = set()
    for item in evidence:
        key = item.quoted_text.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:3]


def _quote_supported(quoted_text: str, source_text: str) -> bool:
    if not quoted_text:
        return False
    return normalize_whitespace(quoted_text).casefold() in normalize_whitespace(source_text).casefold()


def _extract_quote(source_text: str, term: str) -> str | None:
    normalized_term = normalize_whitespace(term)
    if not normalized_term:
        return None
    haystack = normalize_whitespace(source_text)
    index = haystack.casefold().find(normalized_term.casefold())
    if index < 0:
        return None
    start = max(index - 80, 0)
    end = min(index + len(normalized_term) + 120, len(haystack))
    quote = haystack[start:end].strip(" -|,;")
    return truncate_text(quote, 220)


def _candidate_dedup_key(candidate: ContactCandidate) -> str:
    url = _normalize_profile_url(candidate.profile_url)
    if url:
        return url
    return "::".join(
        [
            normalize_whitespace(candidate.full_name or candidate.name or "").casefold(),
            normalize_company_name(candidate.company).casefold(),
        ]
    )


def _extracted_candidate_key(candidate: ExtractedContact, target_company: str) -> str:
    profile_url = _normalize_profile_url(candidate.profile_url or "")
    if profile_url:
        return f"url::{profile_url}"

    name = normalize_whitespace(candidate.name or "").casefold()
    company = normalize_company_name(candidate.company or target_company).casefold()
    if name and company:
        return f"person::{name}::{company}"

    title = normalize_whitespace(candidate.title or "").casefold()
    return stable_cache_key("extracted-candidate", name, title, company, [item.model_dump() for item in candidate.evidence])


def _merge_extracted_contact(left: ExtractedContact, right: ExtractedContact, target_company: str) -> ExtractedContact:
    merged_evidence = _merge_evidence(left.evidence, right.evidence)
    merged_warnings = unique_preserve_order(left.warnings + right.warnings)
    return ExtractedContact(
        name=_prefer_name(left.name, right.name),
        title=_prefer_title(left.title, right.title),
        company=_prefer_company(left.company, right.company, target_company),
        location=_prefer_location(left.location, right.location),
        profile_url=_prefer_profile_url(left.profile_url, right.profile_url),
        public_email=left.public_email or right.public_email,
        evidence=merged_evidence,
        warnings=merged_warnings,
    )


def _merge_contacts(left: ContactCandidate, right: ContactCandidate) -> ContactCandidate:
    best = left if left.score >= right.score else right
    fallback = right if best is left else left
    evidence = _merge_evidence(left.evidence, right.evidence)
    profile_picture_evidence = _merge_profile_picture_evidence(left.profile_picture_evidence, right.profile_picture_evidence)
    source_urls = unique_preserve_order(left.source_urls + right.source_urls)
    warnings = unique_preserve_order(left.warnings + right.warnings)
    merged = best.model_copy(
        update={
            "name": best.name or fallback.name,
            "full_name": best.full_name or fallback.full_name,
            "title": best.title if title_bucket(best.title)[1] >= title_bucket(fallback.title)[1] else fallback.title,
            "location": best.location or fallback.location,
            "company": best.company or fallback.company,
            "profile_url": best.profile_url or fallback.profile_url,
            "public_email": best.public_email or fallback.public_email,
            "source_urls": source_urls,
            "evidence": evidence,
            "profile_picture_url": best.profile_picture_url or fallback.profile_picture_url,
            "profile_picture_source_url": best.profile_picture_source_url or fallback.profile_picture_source_url,
            "profile_picture_confidence": max(best.profile_picture_confidence, fallback.profile_picture_confidence),
            "profile_picture_evidence": profile_picture_evidence,
            "has_profile_picture": best.has_profile_picture or fallback.has_profile_picture,
            "warnings": warnings,
            "is_us_based": best.is_us_based or fallback.is_us_based,
        }
    )
    return merged


def _merge_evidence(left: list[ContactEvidence], right: list[ContactEvidence]) -> list[ContactEvidence]:
    merged: list[ContactEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    for item in left + right:
        key = (item.source_url, item.source_type, item.quoted_text.casefold())
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _merge_profile_picture_evidence(
    left: list[ProfilePictureEvidence],
    right: list[ProfilePictureEvidence],
) -> list[ProfilePictureEvidence]:
    merged: list[ProfilePictureEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    for item in left + right:
        key = (item.source_url, item.image_url, item.discovery_method)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _field_supported(value: str | None, source_text: str) -> bool:
    if not value:
        return False
    return normalize_whitespace(value).casefold() in normalize_whitespace(source_text).casefold()


def _company_supported(value: str | None, source_text: str, target_company: str) -> bool:
    if value and company_match_score(value, target_company, source_text) >= 0.74:
        return True
    normalized_target = normalize_company_name(target_company).casefold()
    normalized_source = normalize_company_name(source_text).casefold()
    return bool(normalized_target and normalized_target in normalized_source)


def _prefer_name(left: str | None, right: str | None) -> str | None:
    return _prefer_longer_text(left, right)


def _prefer_title(left: str | None, right: str | None) -> str | None:
    left_value = normalize_whitespace(left or "")
    right_value = normalize_whitespace(right or "")
    if not left_value:
        return right_value or None
    if not right_value:
        return left_value
    left_score = title_bucket(left_value)[1]
    right_score = title_bucket(right_value)[1]
    if right_score > left_score:
        return right_value
    if left_score > right_score:
        return left_value
    return _prefer_longer_text(left_value, right_value)


def _prefer_company(left: str | None, right: str | None, target_company: str) -> str | None:
    left_value = normalize_whitespace(left or "")
    right_value = normalize_whitespace(right or "")
    if not left_value:
        return right_value or None
    if not right_value:
        return left_value
    left_score = company_match_score(left_value, target_company, left_value)
    right_score = company_match_score(right_value, target_company, right_value)
    if right_score > left_score:
        return right_value
    if left_score > right_score:
        return left_value
    return _prefer_longer_text(left_value, right_value)


def _prefer_location(left: str | None, right: str | None) -> str | None:
    left_value = normalize_whitespace(left or "")
    right_value = normalize_whitespace(right or "")
    if not left_value:
        return right_value or None
    if not right_value:
        return left_value
    left_score = _location_specificity_score(left_value)
    right_score = _location_specificity_score(right_value)
    if right_score > left_score:
        return right_value
    if left_score > right_score:
        return left_value
    return _prefer_longer_text(left_value, right_value)


def _prefer_profile_url(left: str | None, right: str | None) -> str | None:
    left_value = _normalize_profile_url(left or "")
    right_value = _normalize_profile_url(right or "")
    if not left_value:
        return right_value or None
    if not right_value:
        return left_value
    left_score = _profile_url_priority(left_value)
    right_score = _profile_url_priority(right_value)
    if right_score > left_score:
        return right_value
    if left_score > right_score:
        return left_value
    return _prefer_longer_text(left_value, right_value)


def _prefer_longer_text(left: str | None, right: str | None) -> str | None:
    left_value = normalize_whitespace(left or "")
    right_value = normalize_whitespace(right or "")
    if not left_value:
        return right_value or None
    if not right_value:
        return left_value
    return right_value if len(right_value) > len(left_value) else left_value


def _location_specificity_score(value: str) -> int:
    normalized = normalize_whitespace(value)
    if re.search(r"\b[A-Z][A-Za-z.\- ]+,\s*[A-Z]{2}\b", normalized):
        return 4
    if re.search(r"\b(?:Greater\s+)?[A-Z][A-Za-z.\- ]+(?:Metropolitan Area|Bay Area|DC-Baltimore Area|Area)\b", normalized):
        return 3
    if re.search(r"\bRemote\s*[-,]?\s*United States\b", normalized, flags=re.IGNORECASE):
        return 2
    if re.search(r"\b(United States|USA|US)\b", normalized, flags=re.IGNORECASE):
        return 1
    return 0


def _profile_url_priority(url: str) -> int:
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    path = parsed.path.casefold()
    if "linkedin.com" in host and path.startswith("/in/"):
        return 4
    if any(marker in path for marker in ("/team", "/people", "/leadership", "/about", "/company")):
        return 3
    if host:
        return 2
    return 1


def _extract_name(title: str, text: str) -> str | None:
    segments = re.split(r"\s+\||\s+-\s+", title)
    for segment in segments:
        cleaned = normalize_whitespace(segment)
        if _looks_like_person_name(cleaned):
            return cleaned
    for match in re.findall(r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,2}", f"{title} {text}"):
        if _looks_like_person_name(match):
            return match
    return None


def _extract_title(title: str, text: str) -> str | None:
    combined = normalize_whitespace(f"{title} {text}")
    for pattern in TITLE_PATTERNS:
        match = re.search(pattern, combined, flags=re.IGNORECASE)
        if match:
            return normalize_whitespace(match.group(1))
    return None


def _extract_location(text: str) -> str | None:
    value = normalize_whitespace(text)
    for pattern in (
        r"\b([A-Z][A-Za-z.\- ]+,\s*[A-Z]{2})\b",
        r"\b((?:Greater\s+)?[A-Z][A-Za-z.\- ]+(?:Metropolitan Area|Bay Area|DC-Baltimore Area|Area))\b",
        r"\b(Remote\s*[-,]?\s*United States)\b",
        r"\b(United States|USA|US)\b",
    ):
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            location = _clean_location_candidate(match.group(1))
            if location:
                return location
    return None


def _clean_location_candidate(value: str) -> str | None:
    location = normalize_whitespace(value)
    for pattern in (
        r"(Greater\s+[A-Z][A-Za-z.\- ]+ Area)",
        r"([A-Z][A-Za-z.\- ]+ Metropolitan Area)",
        r"([A-Z][A-Za-z.\- ]+ Bay Area)",
        r"([A-Z][A-Za-z.\- ]+ DC-Baltimore Area)",
    ):
        match = re.search(pattern, location, flags=re.IGNORECASE)
        if match:
            location = match.group(1)
            break
    location = re.sub(r"^(LinkedIn|Profile|People)\s+", "", location, flags=re.IGNORECASE)
    location = re.sub(r"\s+\|\s+LinkedIn$", "", location, flags=re.IGNORECASE)
    return normalize_whitespace(location) or None


def _extract_supported_company(text: str, target_company: str, source_url: str) -> str | None:
    normalized_text = normalize_company_name(text).casefold()
    normalized_target = normalize_company_name(target_company).casefold()
    if normalized_target and normalized_target in normalized_text:
        return target_company

    host = urlparse(source_url).netloc.lower().replace("www.", "")
    slug = normalized_target.replace(" ", "")
    if slug and slug in host.replace("-", ""):
        return target_company

    match = re.search(r"\b(?:at|with|for)\s+([A-Z][A-Za-z0-9&.\- ]{1,50})", text)
    if match:
        candidate = normalize_whitespace(match.group(1))
        if company_match_score(candidate, target_company, text) >= 0.74:
            return target_company
        return candidate
    return None


def _looks_like_person_name(value: str) -> bool:
    if not value or any(char.isdigit() for char in value):
        return False
    tokens = value.split()
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    return all(token[:1].isupper() for token in tokens if token)


def _search_result_text(result: SearchResultItem) -> str:
    return normalize_whitespace(" ".join([result.title, result.snippet]))


def _is_promising_result(result: SearchResultItem, *, aggressive: bool = False) -> bool:
    combined = normalize_whitespace(f"{result.title} {result.snippet} {result.url}")
    lowered = combined.casefold()
    host = urlparse(result.url).netloc.casefold()
    if _is_linkedin_profile_url(result.url):
        return True
    if "linkedin.com" in host:
        return False

    recruiter_signal = any(keyword in lowered for keyword in SEARCH_KEYWORDS)
    person_page_signal = any(marker in result.url.casefold() for marker in PERSON_PAGE_HINTS)
    title_signal = title_bucket(combined)[1] >= 0.68
    location_signal = _extract_location(combined) is not None

    if aggressive:
        return recruiter_signal or person_page_signal or title_signal or location_signal
    return recruiter_signal or person_page_signal


def _compact_page_text(html: str, limit: int) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    title = normalize_whitespace(soup.title.get_text(" ", strip=True) if soup.title else "")
    text = normalize_whitespace(" ".join(soup.stripped_strings))
    combined = normalize_whitespace(" ".join([title, text]))
    return truncate_text(combined, limit)


def _load_mock_results(company_name: str) -> list[dict[str, Any]]:
    rows = json.loads(MOCK_FIXTURE_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for block in rows:
        query = normalize_whitespace(str(block.get("query", ""))).replace("Acme", company_name)
        for result in block.get("results", []):
            mutated = dict(result)
            mutated["title"] = normalize_whitespace(str(mutated.get("title", "")).replace("Acme", company_name))
            mutated["snippet"] = normalize_whitespace(str(mutated.get("snippet", "")).replace("Acme", company_name))
            mutated["url"] = _normalize_profile_url(str(mutated.get("url", "")))
            mutated["query"] = query
            mutated["search_source"] = "mock_fixture"
            results.append(mutated)
    return results


def _normalize_profile_url(url: str) -> str:
    parsed = urlparse(normalize_result_url(url))
    if not parsed.scheme or not parsed.netloc:
        return normalize_result_url(url)
    cleaned = parsed._replace(query="", fragment="")
    return urlunparse(cleaned).rstrip("/")


def _is_linkedin_profile_url(url: str) -> bool:
    normalized = _normalize_profile_url(url)
    parsed = urlparse(normalized)
    host = parsed.netloc.casefold()
    path = parsed.path.casefold().rstrip("/")
    return "linkedin.com" in host and path.startswith("/in/")


def _nullable_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = normalize_whitespace(str(value))
    return normalized or None
