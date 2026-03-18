from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuntimeSettings(BaseModel):
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    ollama_temperature: float | None = None
    smtp_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender_email: str | None = None
    smtp_use_tls: bool | None = None


class ResumeSummary(BaseModel):
    name: str | None = None
    education: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    experience_bullets: list[str] = Field(default_factory=list)
    raw_text_excerpt: str = ""


class JobSummary(BaseModel):
    company_name: str
    normalized_company_name: str
    position: str
    job_description: str
    concise_summary: str
    important_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    company_match: float = 0.0
    title_relevance: float = 0.0
    us_confidence: float = 0.0
    source_confidence: float = 0.0
    public_email_bonus: float = 0.0
    total: float = 0.0
    title_bucket: str = "other"


class ContactCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    full_name: str
    title: str
    location: str
    company: str
    profile_url: str
    public_email: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    score: float = 0.0
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    is_us_based: bool = False


class GeneratedEmailPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    contact_id: int | None = None
    subject: str
    body: str
    status: str = "generated"
    model_name: str | None = None
    prompt_version: str = "email_v1"
    warnings: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    normalized_job_summary: JobSummary
    parsed_resume_summary: ResumeSummary
    contacts: list[ContactCandidate] = Field(default_factory=list)
    generated_emails: list[GeneratedEmailPayload] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RegenerateEmailRequest(BaseModel):
    contact_id: int | None = None
    contact: ContactCandidate | None = None
    job_context: JobSummary
    resume_context: ResumeSummary
    runtime_settings: RuntimeSettings | None = None


class SendEmailRequest(BaseModel):
    contact_id: int | None = None
    generated_email_id: int | None = None
    to_email: str
    subject: str
    body: str
    runtime_settings: RuntimeSettings | None = None


class SendEmailResponse(BaseModel):
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    database: str
    ollama_base_url: str
    ollama_model: str
    smtp_enabled: bool


class SettingsTestResponse(BaseModel):
    ok: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

