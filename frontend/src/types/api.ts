export interface ScoreBreakdown {
  company_match: number;
  title_relevance: number;
  us_confidence: number;
  source_confidence: number;
  public_email_bonus: number;
  total: number;
  title_bucket: string;
}

export interface ContactCandidate {
  id?: number;
  full_name: string;
  title: string;
  location: string;
  company: string;
  profile_url: string;
  public_email?: string | null;
  source_urls: string[];
  evidence: string[];
  score: number;
  score_breakdown: ScoreBreakdown;
  is_us_based: boolean;
}

export interface GeneratedEmailPayload {
  id?: number;
  contact_id?: number | null;
  subject: string;
  body: string;
  status: string;
  model_name?: string | null;
  prompt_version: string;
  warnings: string[];
}

export interface ResumeSummary {
  name?: string | null;
  education: string[];
  skills: string[];
  projects: string[];
  experience_bullets: string[];
  raw_text_excerpt: string;
}

export interface JobSummary {
  company_name: string;
  normalized_company_name: string;
  position: string;
  job_description: string;
  concise_summary: string;
  important_skills: string[];
  keywords: string[];
}

export interface AnalyzeResponse {
  normalized_job_summary: JobSummary;
  parsed_resume_summary: ResumeSummary;
  contacts: ContactCandidate[];
  generated_emails: GeneratedEmailPayload[];
  warnings: string[];
}

export interface RuntimeSettingsPayload {
  ollama_base_url?: string;
  ollama_model?: string;
  ollama_temperature?: number;
  smtp_enabled?: boolean;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_sender_email?: string;
  smtp_use_tls?: boolean;
}

export interface SettingsFormValues {
  ollamaBaseUrl: string;
  ollamaModel: string;
  ollamaTemperature: string;
  smtpEnabled: boolean;
  smtpHost: string;
  smtpPort: string;
  smtpUsername: string;
  smtpPassword: string;
  smtpSenderEmail: string;
  smtpUseTls: boolean;
}

export interface SendEmailResponse {
  status: string;
  message: string;
}

export interface SettingsTestResponse {
  ok: boolean;
  message: string;
  details: Record<string, unknown>;
}

