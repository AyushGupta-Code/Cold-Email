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
    <article className="panel overflow-hidden p-0">
      <div className="grid gap-0 xl:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
        <div className="min-w-0 space-y-5 px-5 py-5 md:px-6 md:py-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge label={contact.is_us_based ? "US-based signal" : "Location uncertain"} tone={contact.is_us_based ? "success" : "warning"} />
                <StatusBadge label={`${contact.score.toFixed(1)} score`} tone="accent" />
                <StatusBadge label={hasEmail ? "Public email found" : "No public email"} tone={hasEmail ? "success" : "neutral"} />
              </div>
              <h3 className="mt-4 text-[2rem] font-semibold leading-tight text-slate-950">{contact.full_name}</h3>
              <p className="mt-2 text-lg font-medium text-slate-700">{contact.title}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-sm">
                <InfoChip>{contact.company}</InfoChip>
                <InfoChip>{contact.location}</InfoChip>
                <a
                  className="inline-flex items-center rounded-full border border-teal-300 bg-teal-50 px-3 py-1.5 font-medium text-teal-800 transition hover:border-teal-400 hover:bg-teal-100"
                  href={contact.profile_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  View public profile
                </a>
              </div>
            </div>
            <div className="rounded-[24px] border border-slate-200 bg-stone-50/85 px-4 py-4 lg:min-w-[240px]">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">Verified public email</p>
              <p className="mt-2 break-all text-sm font-semibold leading-6 text-slate-950">{contact.public_email || "Not found from public sources"}</p>
              <p className="mt-3 text-xs leading-5 text-slate-600">
                {hasEmail ? "Used as the default recipient unless you override it below." : "No verified public address was recovered from the gathered sources."}
              </p>
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

        <div className="border-t border-slate-200/90 bg-[linear-gradient(180deg,rgba(247,239,225,0.9),rgba(255,255,255,0.96))] px-5 py-5 md:px-6 md:py-6 xl:border-l xl:border-t-0">
          <div className="flex h-full flex-col gap-5 rounded-[30px] border border-white/70 bg-white/70 p-5 shadow-sm backdrop-blur-sm">
            <div className="flex flex-col gap-4 border-b border-slate-300/80 pb-5 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700">Draft email</p>
                <h4 className="mt-2 text-2xl font-semibold text-slate-950">Edit before sending</h4>
                <p className="mt-2 text-sm leading-6 text-slate-700">The draft stays editable here. Copy it, refine it, or regenerate it before any send action.</p>
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
              <label className="block text-sm font-semibold text-slate-950">
                Subject
                <p className="mt-1 text-sm font-normal leading-6 text-slate-600">Keep the first-touch subject line brief and specific.</p>
                <input className="field" value={emailDraft?.subject ?? ""} onChange={(event) => onDraftChange("subject", event.target.value)} />
              </label>

              <label className="block text-sm font-semibold text-slate-950">
                Email body
                <p className="mt-1 text-sm font-normal leading-6 text-slate-600">Review tone, specificity, and claims before copying or sending.</p>
                <textarea
                  className="field min-h-[260px] resize-y"
                  value={emailDraft?.body ?? ""}
                  onChange={(event) => onDraftChange("body", event.target.value)}
                />
              </label>

              <div className="rounded-[24px] border border-slate-200 bg-stone-50/85 p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Recipient override</p>
                    <p className="mt-1 text-sm leading-6 text-slate-700">Leave blank to use the verified public email when available, or type a manually verified public address.</p>
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
                    <span className="text-sm font-medium text-slate-700">
                      {smtpConfigured ? "Add a recipient email to enable sending." : "Configure SMTP to enable sending."}
                    </span>
                  )}
                  <span className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700">
                    Active recipient: {activeRecipient || "None"}
                  </span>
                </div>
              </div>

              {warnings.length ? (
                <div className="rounded-[24px] border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
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
    <div className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-600">{label}</p>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
    </div>
  );
}

function InfoChip({ children }: { children: string }) {
  return <span className="inline-flex items-center rounded-full border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700">{children}</span>;
}
