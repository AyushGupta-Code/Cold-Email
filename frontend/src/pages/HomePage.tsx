import { FormEvent, startTransition, useEffect, useState } from "react";

import { AppShell } from "../components/AppShell";
import { ContactCard } from "../components/ContactCard";
import { EmptyState } from "../components/EmptyState";
import { ExportActions } from "../components/ExportActions";
import { FormSection } from "../components/FormSection";
import { SettingsPanel } from "../components/SettingsPanel";
import { StageProgress } from "../components/StageProgress";
import { analyzeApplication, regenerateEmail, sendEmail } from "../lib/api";
import { defaultSettings, loadSettings, saveSettings } from "../lib/storage";
import { toRuntimeSettingsPayload } from "../lib/utils";
import type { AnalyzeResponse, ContactCandidate, GeneratedEmailPayload, SettingsFormValues } from "../types/api";

export function HomePage() {
  const [companyName, setCompanyName] = useState("");
  const [position, setPosition] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AnalyzeResponse | null>(null);
  const [settings, setSettings] = useState<SettingsFormValues>(() => {
    if (typeof window === "undefined") {
      return defaultSettings;
    }
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

  return (
    <AppShell>
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
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
        <>
          <section className="panel p-6 md:p-8">
            <div className="grid gap-6 md:grid-cols-[1.15fr_0.85fr]">
              <div>
                <p className="font-display text-sm uppercase tracking-[0.32em] text-spruce">Results</p>
                <h2 className="mt-3 font-display text-3xl text-ink">
                  {results.contacts.length} contact{results.contacts.length === 1 ? "" : "s"} surfaced for {results.normalized_job_summary.company_name}
                </h2>
                <p className="mt-3 text-sm text-slatewarm">{results.normalized_job_summary.concise_summary}</p>
              </div>
              <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5">
                <p className="font-display text-lg text-ink">Warnings and limitations</p>
                <div className="mt-3 space-y-2 text-sm text-slatewarm">
                  {results.warnings.length ? results.warnings.map((warning) => <p key={warning}>{warning}</p>) : <p>No warnings reported.</p>}
                </div>
              </div>
            </div>
          </section>

          {results.contacts.length > 0 ? <ExportActions contacts={results.contacts} emails={results.generated_emails} /> : null}

          {results.contacts.length === 0 ? (
            <EmptyState warnings={results.warnings} />
          ) : (
            <div className="grid gap-6">
              {results.contacts.map((contact) => {
                const key = String(contact.id ?? contact.profile_url);
                const draft = results.generated_emails.find((item) => item.contact_id === contact.id);
                return (
                  <div key={key} className="grid gap-2">
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
                      <p className="px-2 text-sm text-slatewarm">{sendStatus[key]}</p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <EmptyState warnings={errors.length ? errors : ["Run the main form to search public contacts and draft emails."]} />
      )}
    </AppShell>
  );
}
