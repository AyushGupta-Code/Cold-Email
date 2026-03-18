import { FormEvent, startTransition, useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import { ContactCard } from "../components/ContactCard";
import { EmptyState } from "../components/EmptyState";
import { ExportActions } from "../components/ExportActions";
import { FormSection } from "../components/FormSection";
import { SectionCard } from "../components/SectionCard";
import { SettingsPanel } from "../components/SettingsPanel";
import { StageProgress } from "../components/StageProgress";
import { StatusBadge } from "../components/StatusBadge";
import { SummaryBanner } from "../components/SummaryBanner";
import { analyzeApplication, regenerateEmail, sendEmail } from "../lib/api";
import { defaultSettings, loadSettings, saveSettings } from "../lib/storage";
import { toRuntimeSettingsPayload } from "../lib/utils";
import type { AnalyzeResponse, ContactCandidate, GeneratedEmailPayload, SettingsFormValues } from "../types/api";

function statusMessageClass(message: string) {
  if (/sent|success|delivered|ok/i.test(message)) {
    return "border-emerald-300 bg-emerald-50 text-emerald-800";
  }
  if (/failed|error|required|invalid/i.test(message)) {
    return "border-rose-300 bg-rose-50 text-rose-800";
  }
  return "border-slate-300 bg-slate-50 text-slate-700";
}

export function HomePage() {
  const [companyName, setCompanyName] = useState("");
  const [position, setPosition] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AnalyzeResponse | null>(null);
  const [settings, setSettings] = useState<SettingsFormValues>(() => {
    if (typeof window === "undefined") return defaultSettings;
    return loadSettings();
  });
  const [manualRecipients, setManualRecipients] = useState<Record<string, string>>({});
  const [sendStatus, setSendStatus] = useState<Record<string, string>>({});
  const [sendingIds, setSendingIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  function updateForm(field: "companyName" | "position" | "jobDescription", value: string) {
    if (field === "companyName") setCompanyName(value);
    if (field === "position") setPosition(value);
    if (field === "jobDescription") setJobDescription(value);
  }

  function updateSettings<K extends keyof SettingsFormValues>(field: K, value: SettingsFormValues[K]) {
    setSettings((current) => ({ ...current, [field]: value }));
  }

  async function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: string[] = [];
    if (!companyName.trim()) nextErrors.push("Company name is required.");
    if (!position.trim()) nextErrors.push("Position is required.");
    if (!jobDescription.trim()) nextErrors.push("Job description is required.");
    if (!resumeFile) nextErrors.push("Resume upload is required.");
    setErrors(nextErrors);
    if (nextErrors.length > 0 || !resumeFile) return;

    setLoading(true);
    setResults(null);
    setSendStatus({});
    try {
      const response = await analyzeApplication({
        companyName: companyName.trim(),
        position: position.trim(),
        jobDescription: jobDescription.trim(),
        resumeFile,
        runtimeSettings: toRuntimeSettingsPayload(settings),
      });
      startTransition(() => {
        setResults(response);
        const recipients: Record<string, string> = {};
        response.contacts.forEach((contact) => {
          const key = String(contact.id ?? contact.profile_url);
          recipients[key] = contact.public_email ?? "";
        });
        setManualRecipients(recipients);
      });
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Analysis failed."]);
    } finally {
      setLoading(false);
    }
  }

  async function handleRegenerate(contact: ContactCandidate) {
    if (!results) return;
    try {
      const draft = await regenerateEmail({
        contact,
        jobContext: results.normalized_job_summary,
        resumeContext: results.parsed_resume_summary,
        runtimeSettings: toRuntimeSettingsPayload(settings),
      });
      setResults((current) => {
        if (!current) return current;
        const matched = current.generated_emails.some((item) => item.contact_id === contact.id);
        const nextEmails = current.generated_emails.map((item) =>
          item.contact_id === contact.id ? { ...draft, id: item.id ?? draft.id, contact_id: contact.id } : item,
        );
        return {
          ...current,
          generated_emails: matched ? nextEmails : [...nextEmails, { ...draft, contact_id: contact.id }],
        };
      });
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Email regeneration failed."]);
    }
  }

  async function handleSend(contact: ContactCandidate, draft?: GeneratedEmailPayload) {
    if (!draft) return;
    const key = String(contact.id ?? contact.profile_url);
    const recipient = (manualRecipients[key] || contact.public_email || "").trim();
    if (!recipient) {
      setSendStatus((current) => ({ ...current, [key]: "Recipient email is required." }));
      return;
    }

    setSendingIds((current) => ({ ...current, [key]: true }));
    try {
      const response = await sendEmail({
        contactId: contact.id,
        generatedEmailId: draft.id,
        toEmail: recipient,
        subject: draft.subject,
        body: draft.body,
        runtimeSettings: toRuntimeSettingsPayload(settings),
      });
      setSendStatus((current) => ({ ...current, [key]: response.message }));
    } catch (error) {
      setSendStatus((current) => ({ ...current, [key]: error instanceof Error ? error.message : "Send failed." }));
    } finally {
      setSendingIds((current) => ({ ...current, [key]: false }));
    }
  }

  function updateDraft(contactId: number | undefined, field: "subject" | "body", value: string) {
    setResults((current) => {
      if (!current) return current;
      return {
        ...current,
        generated_emails: current.generated_emails.map((draft) =>
          draft.contact_id === contactId ? { ...draft, [field]: value } : draft,
        ),
      };
    });
  }

  const smtpConfigured = settings.smtpEnabled && Boolean(settings.smtpHost.trim()) && Boolean(settings.smtpSenderEmail.trim());
  const verifiedEmailCount = useMemo(() => results?.contacts.filter((contact) => Boolean(contact.public_email)).length ?? 0, [results]);

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,0.9fr)] xl:items-start">
        <FormSection
          companyName={companyName}
          position={position}
          jobDescription={jobDescription}
          resumeFile={resumeFile}
          errors={errors}
          loading={loading}
          onChange={updateForm}
          onFileChange={setResumeFile}
          onSubmit={handleAnalyze}
        />
        <SettingsPanel values={settings} onChange={updateSettings} />
      </div>

      <StageProgress active={loading} />

      {results ? (
        <div className="space-y-6 lg:space-y-7">
          <SectionCard
            eyebrow="Step 3"
            title={`Review results for ${results.normalized_job_summary.company_name}`}
            description={results.normalized_job_summary.concise_summary}
            actions={<StatusBadge label={`${results.contacts.length} contact${results.contacts.length === 1 ? "" : "s"}`} tone="accent" />}
          >
            <SummaryBanner
              contactCount={results.contacts.length}
              verifiedEmailCount={verifiedEmailCount}
              warnings={results.warnings}
            />
          </SectionCard>

          {results.contacts.length > 0 ? <ExportActions contacts={results.contacts} emails={results.generated_emails} /> : null}

          {results.contacts.length === 0 ? (
            <EmptyState warnings={results.warnings} />
          ) : (
            <SectionCard
              eyebrow="Step 4"
              title="Review contacts and draft emails"
              description="Primary details stay visible up front, while evidence, source links, and score reasoning are tucked into on-demand disclosure blocks."
            >
              <div className="grid gap-5">
                {results.contacts.map((contact) => {
                  const key = String(contact.id ?? contact.profile_url);
                  const draft = results.generated_emails.find((item) => item.contact_id === contact.id);
                  return (
                    <div key={key} className="space-y-3">
                      <ContactCard
                        contact={contact}
                        emailDraft={draft}
                        manualRecipient={manualRecipients[key] ?? ""}
                        smtpConfigured={smtpConfigured}
                        sending={Boolean(sendingIds[key])}
                        onRecipientChange={(value) => setManualRecipients((current) => ({ ...current, [key]: value }))}
                        onDraftChange={(field, value) => updateDraft(contact.id, field, value)}
                        onRegenerate={() => handleRegenerate(contact)}
                        onSend={() => handleSend(contact, draft)}
                      />
                      {sendStatus[key] ? (
                        <p className={`rounded-[20px] border px-4 py-3 text-sm leading-6 ${statusMessageClass(sendStatus[key])}`}>{sendStatus[key]}</p>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          )}
        </div>
      ) : (
        <EmptyState warnings={errors} />
      )}
    </AppShell>
  );
}
