from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.entities import Contact
from app.schemas.api import (
    AnalyzeResponse,
    ContactCandidate,
    ContactSearchResponse,
    GeneratedEmailPayload,
    HealthResponse,
    RegenerateEmailRequest,
    RuntimeSettings,
    SendEmailRequest,
    SendEmailResponse,
    SettingsTestResponse,
)
from app.services.contact_discovery import discover_contacts
from app.services.email_generator import generate_email_for_contact, generate_emails_for_contacts, test_ollama_connection
from app.services.job_profile import build_job_profile
from app.services.persistence import create_contacts, create_generated_emails, create_job_and_resume, log_send_attempt
from app.services.resume_parser import parse_resume_bytes
from app.services.smtp_sender import is_smtp_configured, send_email, test_smtp_connection

router = APIRouter(prefix="/api", tags=["recruiter-outreach"])


def merge_settings(base: Settings, overrides: RuntimeSettings | None) -> Settings:
    if overrides is None:
        return base
    return base.model_copy(update=overrides.model_dump(exclude_none=True))


def parse_runtime_settings(raw: str | None) -> RuntimeSettings | None:
    if not raw:
        return None
    try:
        return RuntimeSettings.model_validate(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid settings JSON: {exc}") from exc


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        database="configured",
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        smtp_enabled=is_smtp_configured(settings),
    )


@router.get("/settings/test-ollama", response_model=SettingsTestResponse)
def test_ollama_endpoint(
    settings: Annotated[Settings, Depends(get_settings)],
    base_url: str | None = Query(default=None),
    model: str | None = Query(default=None),
) -> SettingsTestResponse:
    effective = settings.model_copy(
        update={key: value for key, value in {"ollama_base_url": base_url, "ollama_model": model}.items() if value}
    )
    ok, message, raw = test_ollama_connection(effective.ollama_base_url, effective.ollama_model)
    details = json.loads(raw) if raw else {}
    return SettingsTestResponse(ok=ok, message=message, details=details)


@router.get("/settings/test-smtp", response_model=SettingsTestResponse)
def test_smtp_endpoint(
    settings: Annotated[Settings, Depends(get_settings)],
    host: str | None = Query(default=None),
    port: int | None = Query(default=None),
    username: str | None = Query(default=None),
    password: str | None = Query(default=None),
    sender_email: str | None = Query(default=None),
    use_tls: bool | None = Query(default=None),
) -> SettingsTestResponse:
    effective = settings.model_copy(
        update={
            key: value
            for key, value in {
                "smtp_enabled": True if host else settings.smtp_enabled,
                "smtp_host": host,
                "smtp_port": port,
                "smtp_username": username,
                "smtp_password": password,
                "smtp_sender_email": sender_email,
                "smtp_use_tls": use_tls,
            }.items()
            if value is not None and value != ""
        }
    )
    return test_smtp_connection(effective)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    company_name: Annotated[str, Form(...)],
    position: Annotated[str, Form(...)],
    job_description: Annotated[str, Form(...)],
    resume_file: Annotated[UploadFile, File(...)],
    settings_json: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalyzeResponse:
    if not company_name.strip() or not position.strip() or not job_description.strip():
        raise HTTPException(status_code=422, detail="Company, position, and job description are required.")

    effective_settings = merge_settings(settings, parse_runtime_settings(settings_json))
    content = await resume_file.read()
    raw_text, resume_summary, resume_warnings = parse_resume_bytes(resume_file.filename or "resume.txt", content)
    job_summary = build_job_profile(company_name, position, job_description)
    job_row, _ = create_job_and_resume(db, job_summary, resume_file.filename or "resume.txt", raw_text, resume_summary)

    discovery = discover_contacts(job_summary, resume_summary, db, effective_settings)
    created_contacts = create_contacts(db, job_row.id, discovery.contacts)
    contact_warning_map = {
        (item.profile_url, item.full_name or item.name or ""): item.warnings
        for item in discovery.contacts
    }

    api_contacts = [
        ContactCandidate(
            id=row.id,
            name=row.full_name,
            full_name=row.full_name,
            title=row.title,
            location=row.location,
            company=row.company,
            profile_url=row.profile_url,
            public_email=row.public_email,
            source_urls=row.source_urls,
            evidence=row.evidence,
            profile_picture_url=row.profile_picture_url,
            profile_picture_source_url=row.profile_picture_source_url,
            profile_picture_confidence=row.profile_picture_confidence or 0.0,
            profile_picture_evidence=row.profile_picture_evidence or [],
            has_profile_picture=row.has_profile_picture,
            warnings=contact_warning_map.get((row.profile_url, row.full_name), []),
            score=row.score,
            score_breakdown=row.score_breakdown,
            is_us_based=row.is_us_based,
        )
        for row in created_contacts
    ]
    generated_payloads = generate_emails_for_contacts(api_contacts, resume_summary, job_summary, effective_settings)
    generated_payloads = [GeneratedEmailPayload.model_validate(item) for item in generated_payloads]
    created_emails = create_generated_emails(db, job_row.id, generated_payloads)
    api_emails = [
        GeneratedEmailPayload(
            id=row.id,
            contact_id=row.contact_id,
            subject=row.subject,
            body=row.body,
            status=row.status,
            model_name=row.model_name,
            prompt_version=row.prompt_version,
            warnings=row.warnings_json,
        )
        for row in created_emails
    ]

    warnings = resume_warnings + discovery.warnings
    return AnalyzeResponse(
        normalized_job_summary=job_summary,
        parsed_resume_summary=resume_summary,
        contacts=api_contacts,
        generated_emails=api_emails,
        warnings=warnings,
        debug=discovery.debug,
    )


@router.post("/contact-search", response_model=ContactSearchResponse)
async def contact_search(
    company_name: Annotated[str, Form(...)],
    position: Annotated[str, Form(...)],
    job_description: Annotated[str, Form(...)],
    resume_file: Annotated[UploadFile, File(...)],
    settings_json: str | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ContactSearchResponse:
    if not company_name.strip() or not position.strip() or not job_description.strip():
        raise HTTPException(status_code=422, detail="Company, position, and job description are required.")

    effective_settings = merge_settings(settings, parse_runtime_settings(settings_json))
    content = await resume_file.read()
    _, resume_summary, resume_warnings = parse_resume_bytes(resume_file.filename or "resume.txt", content)
    job_summary = build_job_profile(company_name, position, job_description)
    discovery = discover_contacts(job_summary, resume_summary, db, effective_settings)
    discovery.warnings = resume_warnings + discovery.warnings
    return discovery


@router.post("/regenerate-email", response_model=GeneratedEmailPayload)
def regenerate_email(
    request: RegenerateEmailRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> GeneratedEmailPayload:
    effective_settings = merge_settings(settings, request.runtime_settings)
    contact = request.contact
    if contact is None and request.contact_id is not None:
        row = db.get(Contact, request.contact_id)
        if row:
            contact = ContactCandidate(
                id=row.id,
                name=row.full_name,
                full_name=row.full_name,
                title=row.title,
                location=row.location,
                company=row.company,
                profile_url=row.profile_url,
                public_email=row.public_email,
                source_urls=row.source_urls,
                evidence=row.evidence,
                profile_picture_url=row.profile_picture_url,
                profile_picture_source_url=row.profile_picture_source_url,
                profile_picture_confidence=row.profile_picture_confidence or 0.0,
                profile_picture_evidence=row.profile_picture_evidence or [],
                has_profile_picture=row.has_profile_picture,
                score=row.score,
                score_breakdown=row.score_breakdown,
                is_us_based=row.is_us_based,
            )
    if contact is None:
        raise HTTPException(status_code=422, detail="A contact payload or contact_id is required for regeneration.")
    return generate_email_for_contact(contact, request.resume_context, request.job_context, effective_settings)


@router.post("/send-email", response_model=SendEmailResponse)
def send_email_endpoint(
    request: SendEmailRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SendEmailResponse:
    effective_settings = merge_settings(settings, request.runtime_settings)
    success, message = send_email(request, effective_settings)
    log_send_attempt(
        db,
        generated_email_id=request.generated_email_id,
        contact_id=request.contact_id,
        to_email=request.to_email,
        smtp_host=effective_settings.smtp_host or "not-configured",
        status="sent" if success else "failed",
        error_message=None if success else message,
    )
    return SendEmailResponse(status="sent" if success else "failed", message=message)
