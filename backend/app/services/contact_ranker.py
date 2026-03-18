from __future__ import annotations

import re
from urllib.parse import urlparse

from app.schemas.api import ContactCandidate, ScoreBreakdown
from app.services.us_filter import assess_us_location
from app.utils.text import normalize_company_name, normalize_whitespace

TITLE_BUCKETS: list[tuple[str, float, str]] = [
    (r"\b(recruiter|senior recruiter|lead recruiter|staff recruiter)\b", 1.0, "recruiter"),
    (r"\b(talent acquisition|technical recruiter|campus recruiter|university recruiter)\b", 0.95, "recruiter"),
    (r"\b(sourcer|talent sourcer|technical sourcer)\b", 0.9, "sourcer"),
    (r"\b(recruiting coordinator|people partner|hr business partner)\b", 0.72, "recruiting_ops"),
    (r"\b(hiring manager|engineering manager|director|head of)\b", 0.68, "hiring_manager"),
]

SOURCE_DOMAIN_WEIGHTS = {
    "linkedin.com": 0.78,
    "greenhouse.io": 0.72,
    "lever.co": 0.7,
}


def title_bucket(title: str) -> tuple[str, float]:
    normalized = normalize_whitespace(title).lower()
    for pattern, score, bucket in TITLE_BUCKETS:
        if re.search(pattern, normalized):
            return bucket, score
    return "other", 0.2


def is_recruiter_like_title(title: str) -> bool:
    bucket, _ = title_bucket(title)
    return bucket in {"recruiter", "sourcer", "recruiting_ops"}


def score_contact(contact: ContactCandidate, target_company: str, target_position: str) -> ScoreBreakdown:
    normalized_company = normalize_company_name(target_company).casefold()
    contact_company = normalize_company_name(contact.company).casefold()
    bucket, title_score = title_bucket(contact.title)

    company_match = 1.0 if contact_company == normalized_company else 0.6 if normalized_company and normalized_company in contact_company else 0.0
    location_text = " ".join([contact.location, *contact.evidence])
    _, us_confidence, _ = assess_us_location(location_text)

    source_score = 0.35
    parsed = urlparse(contact.profile_url)
    hostname = parsed.netloc.lower()
    for domain, weight in SOURCE_DOMAIN_WEIGHTS.items():
        if domain in hostname:
            source_score = max(source_score, weight)
    if normalized_company and normalized_company.replace(" ", "") in hostname.replace("-", ""):
        source_score = max(source_score, 0.92)
    source_score = min(source_score + min(len(contact.source_urls), 3) * 0.03, 1.0)

    email_bonus = 1.0 if contact.public_email else 0.0
    total = (
        company_match * 30
        + title_score * 30
        + us_confidence * 20
        + source_score * 15
        + email_bonus * 5
    )

    return ScoreBreakdown(
        company_match=round(company_match, 3),
        title_relevance=round(title_score, 3),
        us_confidence=round(us_confidence, 3),
        source_confidence=round(source_score, 3),
        public_email_bonus=round(email_bonus, 3),
        total=round(total, 2),
        title_bucket=bucket,
    )


def rank_contacts(candidates: list[ContactCandidate], target_company: str, target_position: str, limit: int = 5) -> list[ContactCandidate]:
    scored: list[ContactCandidate] = []
    for candidate in candidates:
        candidate.score_breakdown = score_contact(candidate, target_company, target_position)
        candidate.score = candidate.score_breakdown.total
        scored.append(candidate)
    return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

