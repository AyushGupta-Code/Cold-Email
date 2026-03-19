from __future__ import annotations

from functools import lru_cache
import math
import os
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.api import ContactCandidate, JobSummary, ResumeSummary, ScoreBreakdown
from app.services.persistence import cache_artifact, get_cached_artifact
from app.services.us_filter import assess_us_location
from app.utils.text import normalize_company_name, normalize_whitespace, stable_cache_key

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

TITLE_BUCKETS: list[tuple[str, float, str]] = [
    (
        r"\b(technical recruiter|senior recruiter|lead recruiter|staff recruiter|recruiting lead|recruiting manager|recruitment consultant|recruiter)\b",
        1.0,
        "recruiter",
    ),
    (
        r"\b(talent acquisition(?: partner| manager| specialist| advisor| recruiter| lead| consultant)?|talent partner|campus recruiter|campus recruiting|university recruiter|university relations(?: recruiter| manager)?)\b",
        0.96,
        "talent",
    ),
    (r"\b(technical sourcer|talent sourcer|sourcing recruiter|sourcer|sourcing specialist)\b", 0.92, "sourcer"),
    (r"\b(people ops|people operations|people partner|recruiting coordinator|staffing recruiter|staffing manager|staffing)\b", 0.74, "people_ops"),
    (r"\b(hiring manager|engineering manager|software manager|director|head of)\b", 0.7, "hiring_manager"),
]


def title_bucket(title: str) -> tuple[str, float]:
    normalized = normalize_whitespace(title).lower()
    for pattern, score, bucket in TITLE_BUCKETS:
        if re.search(pattern, normalized):
            return bucket, score
    return "other", 0.1


def is_recruiter_like_title(title: str) -> bool:
    _, score = title_bucket(title)
    return score >= 0.72


def rank_contacts(
    candidates: list[ContactCandidate],
    job_summary: JobSummary,
    resume_summary: ResumeSummary,
    settings: Settings,
    db: Session,
    limit: int = 5,
) -> tuple[list[ContactCandidate], list[str]]:
    rerank_scores, warnings = compute_rerank_scores(candidates, job_summary, resume_summary, settings, db)
    scored: list[ContactCandidate] = []

    for candidate in candidates:
        breakdown = score_contact(candidate, job_summary.company_name)
        signature = candidate_signature(candidate)
        retrieval = rerank_scores.get(signature, {})
        bi_encoder_score = retrieval.get("bi_encoder", 0.0)
        cross_encoder_score = retrieval.get("cross_encoder", bi_encoder_score)
        final_score = (
            breakdown.company_match * 0.24
            + breakdown.title_relevance * 0.20
            + breakdown.us_location_confidence * 0.16
            + breakdown.evidence_strength * 0.14
            + breakdown.profile_quality * 0.08
            + breakdown.email_bonus * 0.04
            + breakdown.profile_picture_presence_score * 0.12
            + breakdown.profile_picture_quality_score * 0.06
            + bi_encoder_score * 0.03
            + cross_encoder_score * 0.03
        )
        breakdown.total = round(final_score * 100, 2)
        candidate.score_breakdown = breakdown
        candidate.score = breakdown.total
        scored.append(candidate)

    ordered = sorted(
        scored,
        key=lambda item: (
            item.score,
            item.has_profile_picture,
            item.profile_picture_confidence,
            item.public_email is not None,
            len(item.evidence),
            len(item.source_urls),
        ),
        reverse=True,
    )
    return ordered[:limit], warnings


def score_contact(contact: ContactCandidate, target_company: str) -> ScoreBreakdown:
    bucket, title_score = title_bucket(contact.title)
    evidence_text = " ".join(item.quoted_text for item in contact.evidence)
    company_score = company_match_score(contact.company, target_company, evidence_text)
    _, us_confidence, _ = assess_us_location(" ".join([contact.location, evidence_text]))
    evidence_score = evidence_strength_score(contact)
    profile_score = profile_quality_score(contact.profile_url)
    email_bonus = 1.0 if contact.public_email else 0.0
    profile_picture_presence = 1.0 if contact.has_profile_picture and contact.profile_picture_url else 0.0
    profile_picture_quality = profile_picture_quality_score(contact)

    return ScoreBreakdown(
        company_match=round(company_score, 3),
        title_relevance=round(title_score, 3),
        us_location_confidence=round(us_confidence, 3),
        evidence_strength=round(evidence_score, 3),
        profile_quality=round(profile_score, 3),
        email_bonus=round(email_bonus, 3),
        profile_picture_presence_score=round(profile_picture_presence, 3),
        profile_picture_quality_score=round(profile_picture_quality, 3),
        total=0.0,
        title_bucket=bucket,
    )


def company_match_score(candidate_company: str, target_company: str, evidence_text: str = "") -> float:
    normalized_target = normalize_company_name(target_company).casefold()
    normalized_candidate = normalize_company_name(candidate_company).casefold()
    normalized_evidence = normalize_company_name(evidence_text).casefold()

    if normalized_candidate and normalized_candidate == normalized_target:
        return 1.0
    if normalized_candidate and normalized_target and normalized_target in normalized_candidate:
        return 0.9
    if normalized_candidate and normalized_target:
        similarity = SequenceMatcher(None, normalized_candidate, normalized_target).ratio()
        if similarity >= 0.9:
            return 0.84
        if similarity >= 0.82:
            return 0.76
    if normalized_target and normalized_target in normalized_evidence:
        return 0.74
    return 0.0


def evidence_strength_score(contact: ContactCandidate) -> float:
    if not contact.evidence:
        return 0.0

    unique_sources = len({item.source_url for item in contact.evidence})
    page_evidence = sum(1 for item in contact.evidence if item.source_type == "page")
    quote_lengths = [len(item.quoted_text) for item in contact.evidence if item.quoted_text]
    quote_score = min(sum(quote_lengths) / max(len(quote_lengths), 1), 180) / 180 if quote_lengths else 0.0

    return min(
        0.4
        + min(unique_sources, 3) * 0.18
        + min(page_evidence, 2) * 0.08
        + quote_score * 0.18,
        1.0,
    )


def profile_quality_score(profile_url: str) -> float:
    parsed = urlparse(profile_url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if "linkedin.com" in host and path.startswith("/in/"):
        return 1.0
    if any(marker in path for marker in ("/team", "/people", "/leadership", "/about", "/company")):
        return 0.9
    if any(marker in host for marker in ("greenhouse.io", "lever.co", "workday.com")):
        return 0.76
    if host:
        return 0.62
    return 0.0


def profile_picture_quality_score(contact: ContactCandidate) -> float:
    if not contact.has_profile_picture or not contact.profile_picture_url:
        return 0.0
    return max(0.0, min(float(contact.profile_picture_confidence), 1.0))


def build_query_representation(job_summary: JobSummary, resume_summary: ResumeSummary) -> str:
    recruiter_intent = "recruiter talent acquisition technical recruiter sourcer hiring manager university recruiter united states"
    resume_context = " ".join(resume_summary.skills[:6] + resume_summary.experience_bullets[:4])
    return normalize_whitespace(
        f"{job_summary.company_name} {job_summary.position} {job_summary.concise_summary} {recruiter_intent} {resume_context}"
    )


def candidate_text(candidate: ContactCandidate) -> str:
    evidence_text = " ".join(item.quoted_text for item in candidate.evidence)
    return normalize_whitespace(
        " ".join(
            [
                candidate.full_name or candidate.name or "",
                candidate.title,
                candidate.company,
                candidate.location,
                candidate.profile_url,
                evidence_text,
            ]
        )
    )


def candidate_signature(candidate: ContactCandidate) -> str:
    return stable_cache_key(
        "contact-signature",
        candidate.profile_url,
        candidate.full_name or candidate.name or "",
        candidate.title,
        candidate.company,
    )


def compute_rerank_scores(
    candidates: list[ContactCandidate],
    job_summary: JobSummary,
    resume_summary: ResumeSummary,
    settings: Settings,
    db: Session,
) -> tuple[dict[str, dict[str, float]], list[str]]:
    warnings: list[str] = []
    if not candidates:
        return {}, warnings

    query_repr = build_query_representation(job_summary, resume_summary)
    texts = [candidate_text(candidate) for candidate in candidates]
    signatures = [candidate_signature(candidate) for candidate in candidates]
    cache_key = stable_cache_key(
        "contact-rerank",
        query_repr,
        texts,
        settings.semantic_model,
        settings.semantic_reranker_model,
    )
    cached = get_cached_artifact(db, "contact_rerank_scores", cache_key)
    if isinstance(cached, dict):
        return {str(key): {k: float(v) for k, v in value.items()} for key, value in cached.items() if isinstance(value, dict)}, warnings

    scores = {signature: {"bi_encoder": 0.0, "cross_encoder": 0.0} for signature in signatures}
    bi_scores, bi_warnings = _compute_bi_encoder_scores(query_repr, texts, settings)
    warnings.extend(bi_warnings)
    for signature, score in zip(signatures, bi_scores, strict=False):
        scores[signature]["bi_encoder"] = score

    ranked_indices = sorted(range(len(texts)), key=lambda index: bi_scores[index], reverse=True)[: settings.discovery_bi_encoder_top_k]
    cross_scores, cross_warnings = _compute_cross_encoder_scores(query_repr, texts, ranked_indices, settings)
    warnings.extend(cross_warnings)
    for index, score in cross_scores.items():
        scores[signatures[index]]["cross_encoder"] = score

    cache_artifact(db, "contact_rerank_scores", cache_key, scores)
    return scores, warnings


def _compute_bi_encoder_scores(query_repr: str, texts: list[str], settings: Settings) -> tuple[list[float], list[str]]:
    model = get_bi_encoder(settings.semantic_model)
    if model is None:
        return [0.0 for _ in texts], ["Bi-encoder model unavailable locally; using heuristic ranking only."]

    try:  # pragma: no cover - depends on local model availability
        embeddings = model.encode(texts + [query_repr], normalize_embeddings=True)
        query_embedding = embeddings[-1]
        raw_scores = [float((embeddings[index] * query_embedding).sum()) for index in range(len(texts))]
        return [_normalize_cosine_score(score) for score in raw_scores], []
    except Exception as exc:  # pragma: no cover
        return [0.0 for _ in texts], [f"Bi-encoder scoring failed: {exc}"]


def _compute_cross_encoder_scores(
    query_repr: str,
    texts: list[str],
    ranked_indices: list[int],
    settings: Settings,
) -> tuple[dict[int, float], list[str]]:
    model = get_cross_encoder(settings.semantic_reranker_model)
    if model is None:
        return {}, ["Cross-encoder reranker unavailable locally; bi-encoder scores were not refined."]

    if not ranked_indices:
        return {}, []

    top_indices = ranked_indices[: settings.discovery_cross_encoder_top_k]
    try:  # pragma: no cover - depends on local model availability
        raw_scores = model.predict([(query_repr, texts[index]) for index in top_indices])
        return {index: _sigmoid(float(score)) for index, score in zip(top_indices, raw_scores, strict=False)}, []
    except Exception as exc:  # pragma: no cover
        return {}, [f"Cross-encoder reranking failed: {exc}"]


def _normalize_cosine_score(score: float) -> float:
    return round(max(min((score + 1.0) / 2.0, 1.0), 0.0), 4)


def _sigmoid(score: float) -> float:
    if 0.0 <= score <= 1.0:
        return round(score, 4)
    return round(1.0 / (1.0 + math.exp(-score)), 4)


@lru_cache(maxsize=1)
def _get_sentence_transformer_class():
    try:  # pragma: no cover - dependency availability depends on environment
        from sentence_transformers import SentenceTransformer
    except Exception:  # pragma: no cover
        return None
    return SentenceTransformer


@lru_cache(maxsize=1)
def _get_cross_encoder_class():
    try:  # pragma: no cover - dependency availability depends on environment
        from sentence_transformers import CrossEncoder
    except Exception:  # pragma: no cover
        return None
    return CrossEncoder


@lru_cache(maxsize=4)
def get_bi_encoder(model_name: str):
    transformer_cls = _get_sentence_transformer_class()
    if transformer_cls is None:
        return None
    try:  # pragma: no cover
        return transformer_cls(model_name, local_files_only=True)
    except Exception:
        return None


@lru_cache(maxsize=4)
def get_cross_encoder(model_name: str):
    cross_encoder_cls = _get_cross_encoder_class()
    if cross_encoder_cls is None:
        return None
    try:  # pragma: no cover
        return cross_encoder_cls(model_name, local_files_only=True)
    except Exception:
        return None
