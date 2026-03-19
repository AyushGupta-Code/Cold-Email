from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import Contact, GeneratedEmail, Job, Resume, SearchCache, SendLog
from app.schemas.api import ContactCandidate, GeneratedEmailPayload, JobSummary, ResumeSummary


def create_job_and_resume(
    db: Session,
    job_summary: JobSummary,
    resume_filename: str,
    resume_raw_text: str,
    resume_summary: ResumeSummary,
) -> tuple[Job, Resume]:
    job = Job(
        company_name=job_summary.company_name,
        normalized_company_name=job_summary.normalized_company_name,
        position=job_summary.position,
        job_description=job_summary.job_description,
        job_summary=job_summary.concise_summary,
        extracted_keywords=job_summary.important_skills,
    )
    db.add(job)
    db.flush()

    resume = Resume(
        job_id=job.id,
        filename=resume_filename,
        raw_text=resume_raw_text,
        summary_json=resume_summary.model_dump(),
    )
    db.add(resume)
    db.commit()
    db.refresh(job)
    db.refresh(resume)
    return job, resume


def create_contacts(db: Session, job_id: int, contacts: list[ContactCandidate]) -> list[Contact]:
    rows: list[Contact] = []
    for item in contacts:
        row = Contact(
            job_id=job_id,
            full_name=item.full_name or item.name or "",
            title=item.title,
            location=item.location,
            company=item.company,
            profile_url=item.profile_url,
            public_email=item.public_email,
            source_urls=item.source_urls,
            evidence=[entry.model_dump() for entry in item.evidence],
            profile_picture_url=item.profile_picture_url,
            profile_picture_source_url=item.profile_picture_source_url,
            profile_picture_confidence=item.profile_picture_confidence,
            profile_picture_evidence=[entry.model_dump() for entry in item.profile_picture_evidence],
            has_profile_picture=item.has_profile_picture,
            score=item.score,
            score_breakdown=item.score_breakdown.model_dump(),
            is_us_based=item.is_us_based,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def create_generated_emails(
    db: Session,
    job_id: int,
    emails: list[GeneratedEmailPayload],
) -> list[GeneratedEmail]:
    rows: list[GeneratedEmail] = []
    for item in emails:
        row = GeneratedEmail(
            job_id=job_id,
            contact_id=item.contact_id or 0,
            subject=item.subject,
            body=item.body,
            status=item.status,
            model_name=item.model_name,
            prompt_version=item.prompt_version,
            warnings_json=item.warnings,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def update_generated_email(db: Session, generated_email_id: int, payload: GeneratedEmailPayload) -> GeneratedEmail | None:
    row = db.get(GeneratedEmail, generated_email_id)
    if not row:
        return None
    row.subject = payload.subject
    row.body = payload.body
    row.status = payload.status
    row.model_name = payload.model_name
    row.prompt_version = payload.prompt_version
    row.warnings_json = payload.warnings
    db.commit()
    db.refresh(row)
    return row


def log_send_attempt(
    db: Session,
    *,
    generated_email_id: int | None,
    contact_id: int | None,
    to_email: str,
    smtp_host: str,
    status: str,
    error_message: str | None = None,
) -> SendLog:
    row = SendLog(
        generated_email_id=generated_email_id,
        contact_id=contact_id,
        to_email=to_email,
        smtp_host=smtp_host,
        status=status,
        error_message=error_message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_cached_artifact(db: Session, source: str, query: str) -> Any | None:
    now = datetime.utcnow()
    statement = (
        select(SearchCache)
        .where(SearchCache.source == source)
        .where(SearchCache.query == query)
        .where(SearchCache.expires_at >= now)
        .order_by(SearchCache.cached_at.desc())
    )
    row = db.execute(statement).scalars().first()
    return row.results_json if row else None


def cache_artifact(db: Session, source: str, query: str, results: Any) -> None:
    db.execute(delete(SearchCache).where(SearchCache.source == source).where(SearchCache.query == query))
    row = SearchCache(
        source=source,
        query=query,
        results_json=results,
        expires_at=datetime.utcnow() + timedelta(days=2),
    )
    db.add(row)
    db.commit()


def get_cached_search(db: Session, source: str, query: str) -> list[dict[str, Any]] | None:
    cached = get_cached_artifact(db, source, query)
    return cached if isinstance(cached, list) and cached else None


def cache_search_results(db: Session, source: str, query: str, results: list[dict[str, Any]]) -> None:
    if not results:
        return
    cache_artifact(db, source, query, results)
