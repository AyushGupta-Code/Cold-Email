import { CollapsibleDetails } from "./CollapsibleDetails";
import { StatusBadge } from "./StatusBadge";
import { copyText } from "../lib/utils";
import type { ContactCandidate, GeneratedEmailPayload } from "../types/api";

interface ContactCardProps {
  contact: ContactCandidate;
  emailDraft?: GeneratedEmailPayload;
  manualRecipient: string;
  smtpConfigured: boolean;
  sending: boolean;
  onRecipientChange: (value: string) => void;
  onDraftChange: (field: "subject" | "body", value: string) => void;
  onRegenerate: () => void;
  onSend: () => void;
}

export function ContactCard(props: ContactCardProps) {
  const { contact, emailDraft, manualRecipient, smtpConfigured, sending, onRecipientChange, onDraftChange, onRegenerate, onSend } = props;
  const activeRecipient = manualRecipient.trim() || contact.public_email || "";
  const canSend = smtpConfigured && Boolean(activeRecipient);
  const score = contact.score_breakdown;
  const warnings = emailDraft?.warnings ?? [];
  const hasEmail = Boolean(contact.public_email);

  return (
    <article className="panel overflow-hidden p-5 md:p-6">
      <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1 space-y-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge label={contact.is_us_based ? "US-based signal" : "Location uncertain"} tone={contact.is_us_based ? "success" : "warning"} />
                <StatusBadge label={`${contact.score.toFixed(1)} score`} tone="accent" />
                <StatusBadge label={hasEmail ? "Public email found" : "No public email"} tone={hasEmail ? "success" : "neutral"} />
              </div>
              <h3 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">{contact.full_name}</h3>
              <p className="mt-1 text-base text-slate-600">{contact.title}</p>
              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-500">
                <span>{contact.company}</span>
                <span>{contact.location}</span>
                <a className="font-medium text-teal-700 hover:text-teal-800" href={contact.profile_url} rel="noreferrer" target="_blank">
                  View public profile
                </a>
              </div>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 lg:min-w-[220px]">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Verified public email</p>
              <p className="mt-2 break-all text-sm font-medium text-slate-900">{contact.public_email || "Not found from public sources"}</p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Meta label="Company match" value={String(score.company_match)} />
            <Meta label="Title relevance" value={String(score.title_relevance)} />
            <Meta label="Source confidence" value={String(score.source_confidence)} />
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <CollapsibleDetails title="Source URLs" summary={`${contact.source_urls.length} public links used for this contact.`}>
              <ul className="space-y-2 text-sm text-slate-600">
                {contact.source_urls.map((source) => (
                  <li key={source} className="break-all">
                    <a className="text-teal-700 underline decoration-teal-200 underline-offset-4" href={source} rel="noreferrer" target="_blank">
                      {source}
                    </a>
                  </li>
                ))}
              </ul>
            </CollapsibleDetails>

            <CollapsibleDetails title="Evidence and score breakdown" summary="Detailed rationale stays available, but secondary to the review workflow.">
              <div className="space-y-3 text-sm text-slate-600">
                <div className="grid gap-2 sm:grid-cols-2">
                  <Meta label="US confidence" value={String(score.us_confidence)} />
                  <Meta label="Email bonus" value={String(score.public_email_bonus)} />
                  <Meta label="Title bucket" value={score.title_bucket} />
                  <Meta label="Total" value={String(score.total)} />
                </div>
                {contact.evidence.length ? (
                  <div>
                    <p className="font-semibold text-slate-900">Evidence</p>
                    <ul className="mt-2 space-y-2">
                      {contact.evidence.map((item) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </CollapsibleDetails>
          </div>
        </div>

        <div className="w-full xl:max-w-xl">
          <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Draft email</p>
                <p className="mt-1 text-sm text-slate-500">Review, edit, and copy before sending.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="button-secondary" onClick={() => copyText(emailDraft?.subject ?? "")} type="button">
                  Copy subject
                </button>
                <button className="button-secondary" onClick={() => copyText(emailDraft?.body ?? "")} type="button">
                  Copy email
                </button>
                <button className="button-secondary" onClick={onRegenerate} type="button">
                  Regenerate
                </button>
              </div>
            </div>

            <div className="mt-4 space-y-4">
              <label className="block text-sm font-medium text-slate-900">
                Subject
                <input className="field" value={emailDraft?.subject ?? ""} onChange={(event) => onDraftChange("subject", event.target.value)} />
              </label>

              <label className="block text-sm font-medium text-slate-900">
                Email body
                <textarea
                  className="field min-h-[260px] resize-y"
                  value={emailDraft?.body ?? ""}
                  onChange={(event) => onDraftChange("body", event.target.value)}
                />
              </label>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Recipient override</p>
                    <p className="mt-1 text-sm text-slate-500">Secondary control for manual send review. Leave blank to use the verified public email when available.</p>
                  </div>
                  <StatusBadge label={activeRecipient ? "Recipient ready" : "Recipient missing"} tone={activeRecipient ? "success" : "warning"} />
                </div>
                <input
                  className="field"
                  placeholder={contact.public_email ?? "Enter a verified public address manually"}
                  value={manualRecipient}
                  onChange={(event) => onRecipientChange(event.target.value)}
                />
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {canSend ? (
                    <button className="button-primary" disabled={sending} onClick={onSend} type="button">
                      {sending ? "Sending..." : "Send email"}
                    </button>
                  ) : (
                    <span className="text-sm text-slate-500">
                      {smtpConfigured ? "Add a recipient email to enable sending." : "Configure SMTP to enable sending."}
                    </span>
                  )}
                  <span className="text-sm text-slate-500">Active recipient: {activeRecipient || "None"}</span>
                </div>
              </div>

              {warnings.length ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-800">
                  {warnings.map((warning) => (
                    <p key={warning}>• {warning}</p>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}
