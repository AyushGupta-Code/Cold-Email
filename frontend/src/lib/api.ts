import type {
  AnalyzeResponse,
  ContactCandidate,
  GeneratedEmailPayload,
  JobSummary,
  ResumeSummary,
  RuntimeSettingsPayload,
  SendEmailResponse,
  SettingsTestResponse,
} from "../types/api";

export async function analyzeApplication(input: {
  companyName: string;
  position: string;
  jobDescription: string;
  resumeFile: File;
  runtimeSettings: RuntimeSettingsPayload;
}): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("company_name", input.companyName);
  form.append("position", input.position);
  form.append("job_description", input.jobDescription);
  form.append("resume_file", input.resumeFile);
  form.append("settings_json", JSON.stringify(input.runtimeSettings));

  const response = await fetch("/api/analyze", {
    method: "POST",
    body: form,
  });
  return handleJsonResponse<AnalyzeResponse>(response);
}

export async function regenerateEmail(input: {
  contact: ContactCandidate;
  jobContext: JobSummary;
  resumeContext: ResumeSummary;
  runtimeSettings: RuntimeSettingsPayload;
}): Promise<GeneratedEmailPayload> {
  const response = await fetch("/api/regenerate-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contact: input.contact,
      job_context: input.jobContext,
      resume_context: input.resumeContext,
      runtime_settings: input.runtimeSettings,
    }),
  });
  return handleJsonResponse<GeneratedEmailPayload>(response);
}

export async function sendEmail(input: {
  contactId?: number;
  generatedEmailId?: number;
  toEmail: string;
  subject: string;
  body: string;
  runtimeSettings: RuntimeSettingsPayload;
}): Promise<SendEmailResponse> {
  const response = await fetch("/api/send-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contact_id: input.contactId,
      generated_email_id: input.generatedEmailId,
      to_email: input.toEmail,
      subject: input.subject,
      body: input.body,
      runtime_settings: input.runtimeSettings,
    }),
  });
  return handleJsonResponse<SendEmailResponse>(response);
}

export async function testOllama(baseUrl: string, model: string): Promise<SettingsTestResponse> {
  const params = new URLSearchParams();
  if (baseUrl.trim()) params.set("base_url", baseUrl.trim());
  if (model.trim()) params.set("model", model.trim());
  const response = await fetch(`/api/settings/test-ollama?${params.toString()}`);
  return handleJsonResponse<SettingsTestResponse>(response);
}

export async function testSmtp(input: {
  host: string;
  port: string;
  username: string;
  password: string;
  senderEmail: string;
  useTls: boolean;
}): Promise<SettingsTestResponse> {
  const params = new URLSearchParams();
  if (input.host.trim()) params.set("host", input.host.trim());
  if (input.port.trim()) params.set("port", input.port.trim());
  if (input.username.trim()) params.set("username", input.username.trim());
  if (input.password) params.set("password", input.password);
  if (input.senderEmail.trim()) params.set("sender_email", input.senderEmail.trim());
  params.set("use_tls", String(input.useTls));
  const response = await fetch(`/api/settings/test-smtp?${params.toString()}`);
  return handleJsonResponse<SettingsTestResponse>(response);
}

async function handleJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Ignore parse failures.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

