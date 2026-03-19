from __future__ import annotations

import json
import re
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.api import JobSummary, ResumeSummary
from app.services.persistence import cache_artifact, get_cached_artifact
from app.utils.text import normalize_company_name, normalize_whitespace, stable_cache_key, truncate_text, unique_preserve_order

QUERY_EXPANSION_SOURCE = "contact_query_expansion"
EXTRACTION_SOURCE = "contact_candidate_extraction"
QUERY_SIGNAL_TERMS = (
    "recruit",
    "talent",
    "sourc",
    "hiring",
    "staffing",
    "campus",
    "university",
    "people",
    "careers",
    "linkedin",
    "team",
)


def expand_queries_with_ollama(
    job_summary: JobSummary,
    resume_summary: ResumeSummary,
    db: Session,
    settings: Settings,
) -> tuple[list[str], list[str], bool]:
    cache_key = stable_cache_key(
        "contact-query-expansion",
        job_summary.model_dump(),
        {
            "skills": resume_summary.skills[:8],
            "projects": resume_summary.projects[:3],
            "experience_bullets": resume_summary.experience_bullets[:3],
        },
    )
    cached = get_cached_artifact(db, QUERY_EXPANSION_SOURCE, cache_key)
    if isinstance(cached, list):
        return [normalize_whitespace(str(item)) for item in cached if normalize_whitespace(str(item))], [], True

    prompt = _query_expansion_prompt(job_summary, resume_summary, settings.discovery_query_target_count)
    payload, error = _ollama_json_completion(prompt, settings)
    if error:
        return [], [f"Ollama query expansion unavailable: {error}"], False

    queries = payload.get("queries", []) if isinstance(payload, dict) else []
    cleaned = _clean_generated_queries(queries, job_summary.company_name, settings.discovery_query_target_count)
    if not cleaned:
        return [], ["Ollama query expansion returned no usable queries."], False

    cache_artifact(db, QUERY_EXPANSION_SOURCE, cache_key, cleaned)
    return cleaned, [], True


def extract_candidates_with_ollama(
    *,
    source_url: str,
    source_type: str,
    source_text: str,
    job_summary: JobSummary,
    settings: Settings,
    db: Session,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    compact_text = truncate_text(source_text, settings.discovery_max_extraction_chars)
    cache_key = stable_cache_key(
        "contact-candidate-extraction",
        source_url,
        source_type,
        compact_text,
        job_summary.company_name,
        job_summary.position,
    )
    cached = get_cached_artifact(db, EXTRACTION_SOURCE, cache_key)
    if isinstance(cached, list):
        return cached, [], True

    prompt = _candidate_extraction_prompt(
        company_name=job_summary.company_name,
        position=job_summary.position,
        source_url=source_url,
        source_type=source_type,
        source_text=compact_text,
    )
    payload, error = _ollama_json_completion(prompt, settings)
    if error:
        return [], [f"Ollama extraction unavailable for {source_url}: {error}"], False

    raw_candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
    cleaned_candidates: list[dict[str, Any]] = []
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            continue
        evidence = raw_candidate.get("evidence", [])
        cleaned_evidence: list[dict[str, str]] = []
        if isinstance(evidence, list):
            for item in evidence:
                if not isinstance(item, dict):
                    continue
                quoted_text = truncate_text(normalize_whitespace(str(item.get("quoted_text", ""))), 240)
                if not quoted_text:
                    continue
                cleaned_evidence.append(
                    {
                        "source_url": normalize_whitespace(str(item.get("source_url") or source_url)),
                        "source_type": "page" if source_type == "page" else "search_snippet",
                        "quoted_text": quoted_text,
                    }
                )
        cleaned_candidates.append(
            {
                "name": _nullable_str(raw_candidate.get("name")),
                "title": _nullable_str(raw_candidate.get("title")),
                "company": _nullable_str(raw_candidate.get("company")),
                "location": _nullable_str(raw_candidate.get("location")),
                "profile_url": _nullable_str(raw_candidate.get("profile_url")) or source_url,
                "public_email": _nullable_str(raw_candidate.get("public_email")),
                "evidence": cleaned_evidence,
            }
        )

    cache_artifact(db, EXTRACTION_SOURCE, cache_key, cleaned_candidates)
    return cleaned_candidates, [], True


def _ollama_json_completion(prompt: str, settings: Settings) -> tuple[dict[str, Any], str | None]:
    try:
        response = requests.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": min(settings.ollama_temperature, 0.2)},
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        raw = str(payload.get("response", "")).strip().strip("`")
        parsed = _parse_json_payload(raw)
        if parsed is None:
            return {}, "response was not valid JSON"
        return parsed, None
    except Exception as exc:
        return {}, str(exc)


def _parse_json_payload(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _query_expansion_prompt(job_summary: JobSummary, resume_summary: ResumeSummary, target_count: int) -> str:
    resume_context = "; ".join(resume_summary.skills[:6] + resume_summary.experience_bullets[:3]) or "Resume summary unavailable."
    return f"""
You generate public-web search queries for a local recruiter contact search pipeline.
Return strict JSON only in this shape:
{{"queries":["query 1","query 2"]}}

Rules:
- Generate exactly {max(24, min(target_count, 30))} queries.
- Use only public-web discovery queries.
- Every query must start with `site:linkedin.com/in`.
- Prefer recruiter, technical recruiter, talent acquisition, sourcer, hiring manager, university recruiter.
- Prefer US-only queries.
- Every query must include the company name or a likely company-domain hint.
- Every query must include at least one contact-search signal such as recruiter, recruiting, talent acquisition, sourcer, hiring manager, staffing, campus, or university.
- All queries must target individual LinkedIn profile pages only.
- Include role-specific variations tied to the target position.
- Include campus/university recruiting variations.
- Avoid generic brand, culture, consulting, news, company-overview, or company page queries.
- Do not add explanations.

Company: {job_summary.company_name}
Position: {job_summary.position}
Job summary: {job_summary.concise_summary}
Resume relevance hints: {resume_context}
Target query count: {target_count}
""".strip()


def _candidate_extraction_prompt(
    *,
    company_name: str,
    position: str,
    source_url: str,
    source_type: str,
    source_text: str,
) -> str:
    return f"""
You extract recruiter-style contact candidates from one public source.
Return strict JSON only in this shape:
{{
  "candidates": [
    {{
      "name": "string or null",
      "title": "string or null",
      "company": "string or null",
      "location": "string or null",
      "profile_url": "string or null",
      "public_email": "string or null",
      "evidence": [
        {{
          "source_url": "{source_url}",
          "source_type": "{source_type}",
          "quoted_text": "short exact support text"
        }}
      ]
    }}
  ]
}}

Rules:
- Extract zero or more candidates.
- Use null whenever unsupported.
- Do not infer or guess missing fields.
- public_email must be null unless explicitly present in the source text.
- quoted_text must be short and copied exactly or near-exactly from the source text.
- Only extract recruiter, technical recruiter, talent acquisition, sourcer, hiring manager, university recruiter, campus recruiter, or closely related staffing contacts.
- The LLM is not a source of truth. Unsupported fields must be null.

Target company: {company_name}
Target position: {position}
Source URL: {source_url}
Source type: {source_type}
Source text:
{source_text}
""".strip()


def _nullable_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = normalize_whitespace(str(value))
    return normalized or None


def _clean_generated_queries(raw_queries: list[Any], company_name: str, target_count: int) -> list[str]:
    company_tokens = _company_query_tokens(company_name)
    cleaned: list[str] = []
    for item in raw_queries:
        if not isinstance(item, str):
            continue
        query = _normalize_linkedin_query(item)
        lowered = query.casefold()
        if not query:
            continue
        if company_tokens and not any(token in lowered for token in company_tokens):
            continue
        if not any(signal in lowered for signal in QUERY_SIGNAL_TERMS):
            continue
        cleaned.append(query)
    return unique_preserve_order(cleaned)[: max(target_count, 15)]


def _normalize_linkedin_query(value: Any) -> str:
    query = normalize_whitespace(str(value))
    if not query:
        return ""
    lowered = query.casefold()
    if "site:linkedin.com/in" in lowered:
        return query
    if lowered.startswith("site:linkedin.com/"):
        query = re.sub(r"site:linkedin\.com/[^\s]+", "site:linkedin.com/in", query, flags=re.IGNORECASE)
        return normalize_whitespace(query)
    return normalize_whitespace(f"site:linkedin.com/in {query}")


def _company_query_tokens(company_name: str) -> set[str]:
    normalized = normalize_company_name(company_name).casefold()
    slug = normalized.replace(" ", "")
    tokens = {token for token in normalized.split() if len(token) >= 3}
    if slug:
        tokens.add(slug)
    return tokens
