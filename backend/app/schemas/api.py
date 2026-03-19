from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ContactEvidence(BaseModel):
    source_url: str
    source_type: Literal["search_snippet", "page"]
    quoted_text: str


class ProfilePictureEvidence(BaseModel):
    source_url: str
    source_type: Literal["page"]
    image_url: str
    discovery_method: Literal["og_image", "twitter_image", "json_ld", "img_tag"]
    context_text: str = ""
    alt_text: str | None = None


class ContactSearchDebug(BaseModel):
    queries_generated: list[str] = Field(default_factory=list)
    heuristic_queries_generated: list[str] = Field(default_factory=list)
    llm_queries_generated: list[str] = Field(default_factory=list)
    urls_considered: int = 0
    pages_fetched: int = 0
    candidates_extracted: int = 0
    candidates_after_filtering: int = 0


class ScoreBreakdown(BaseModel):
    company_match: float = 0.0
    title_relevance: float = 0.0
    us_location_confidence: float = 0.0
    evidence_strength: float = 0.0
    profile_quality: float = 0.0
    email_bonus: float = 0.0
    profile_picture_presence_score: float = 0.0
    profile_picture_quality_score: float = 0.0
    total: float = 0.0
    title_bucket: str = "other"
    us_confidence: float = 0.0
    source_confidence: float = 0.0
    public_email_bonus: float = 0.0

    @model_validator(mode="after")
    def sync_legacy_fields(self) -> "ScoreBreakdown":
        self.us_confidence = self.us_location_confidence
        self.source_confidence = self.profile_quality
        self.public_email_bonus = self.email_bonus
        return self


class ContactCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str | None = None
    full_name: str | None = None
    title: str
    location: str
    company: str
    profile_url: str
    public_email: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    evidence: list[ContactEvidence] = Field(default_factory=list)
    profile_picture_url: str | None = None
    profile_picture_source_url: str | None = None
    profile_picture_confidence: float = 0.0
    profile_picture_evidence: list[ProfilePictureEvidence] = Field(default_factory=list)
    has_profile_picture: bool = False
    warnings: list[str] = Field(default_factory=list)
    score: float = 0.0
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    is_us_based: bool = False

    @model_validator(mode="after")
    def sync_name_fields(self) -> "ContactCandidate":
        if not self.name and self.full_name:
            self.name = self.full_name
        if not self.full_name and self.name:
            self.full_name = self.name
        return self

    @model_validator(mode="after")
    def sync_profile_picture_fields(self) -> "ContactCandidate":
        has_url = bool(self.profile_picture_url and self.profile_picture_source_url)
        has_evidence = bool(self.profile_picture_evidence)
        self.has_profile_picture = bool(self.has_profile_picture or (has_url and has_evidence))
        if not self.has_profile_picture:
            self.profile_picture_confidence = 0.0
        return self


class ContactSearchResponse(BaseModel):
    contacts: list[ContactCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    debug: ContactSearchDebug = Field(default_factory=ContactSearchDebug)


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
    debug: ContactSearchDebug = Field(default_factory=ContactSearchDebug)


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
