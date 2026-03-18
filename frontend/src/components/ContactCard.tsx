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

  return (
    <article className="panel overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-[0.92fr_1.08fr]">
        <div className="border-b border-slate-200 p-6 lg:border-b-0 lg:border-r">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="font-display text-2xl text-ink">{contact.full_name}</h3>
              <p className="mt-2 text-sm text-slatewarm">{contact.title}</p>
            </div>
            <div className="rounded-full bg-ink px-3 py-1 text-sm font-semibold text-white">{contact.score.toFixed(1)}</div>
          </div>

          <dl className="mt-6 space-y-3 text-sm">
            <div>
              <dt className="font-semibold text-ink">Company</dt>
              <dd className="text-slatewarm">{contact.company}</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Location</dt>
              <dd className="text-slatewarm">{contact.location}</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Public profile</dt>
              <dd className="text-slatewarm">
                <a className="underline decoration-spruce decoration-2 underline-offset-4" href={contact.profile_url} rel="noreferrer" target="_blank">
                  {contact.profile_url}
                </a>
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Verified public email</dt>
              <dd className="text-slatewarm">{contact.public_email || "Not found from public sources"}</dd>
            </div>
          </dl>

          <div className="mt-6 rounded-[24px] border border-slate-200 bg-slate-50 p-4">
            <h4 className="font-display text-lg">Source URLs</h4>
            <ul className="mt-3 space-y-2 text-sm text-slatewarm">
              {contact.source_urls.map((source) => (
                <li key={source}>
                  <a className="underline decoration-ember decoration-2 underline-offset-4" href={source} rel="noreferrer" target="_blank">
                    {source}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <details className="mt-5 rounded-[24px] border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-semibold text-ink">Score breakdown and evidence</summary>
            <div className="mt-4 space-y-2 text-sm text-slatewarm">
              <p>Company match: {score.company_match}</p>
              <p>Title relevance: {score.title_relevance}</p>
              <p>US confidence: {score.us_confidence}</p>
              <p>Source confidence: {score.source_confidence}</p>
              <p>Email bonus: {score.public_email_bonus}</p>
              <p>Bucket: {score.title_bucket}</p>
              {contact.evidence.length ? (
                <>
                  <p className="pt-2 font-semibold text-ink">Evidence</p>
                  {contact.evidence.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </>
              ) : null}
            </div>
          </details>
        </div>

        <div className="p-6">
          <div className="flex flex-wrap items-center gap-3">
            <button className="button-secondary" onClick={() => copyText(emailDraft?.subject ?? "")} type="button">
              Copy subject
            </button>
            <button className="button-secondary" onClick={() => copyText(emailDraft?.body ?? "")} type="button">
              Copy email
            </button>
            <button className="button-secondary" onClick={onRegenerate} type="button">
              Regenerate email
            </button>
          </div>

          <label className="mt-5 block text-sm font-medium text-ink">
            Subject
            <input
              className="field"
              value={emailDraft?.subject ?? ""}
              onChange={(event) => onDraftChange("subject", event.target.value)}
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-ink">
            Editable draft
            <textarea
              className="field min-h-60 resize-y"
              value={emailDraft?.body ?? ""}
              onChange={(event) => onDraftChange("body", event.target.value)}
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-ink">
            Recipient email override
            <input
              className="field"
              placeholder={contact.public_email ?? "Enter a verified public address manually"}
              value={manualRecipient}
              onChange={(event) => onRecipientChange(event.target.value)}
            />
            <span className="mt-2 block text-xs text-slatewarm">
              The send button appears only when SMTP is configured and a recipient address exists.
            </span>
          </label>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            {canSend ? (
              <button className="button-primary" disabled={sending} onClick={onSend} type="button">
                {sending ? "Sending..." : "Send email"}
              </button>
            ) : (
              <span className="rounded-full bg-slate-100 px-4 py-2 text-sm text-slatewarm">
                {smtpConfigured ? "Add a recipient email to enable sending." : "Configure SMTP to enable sending."}
              </span>
            )}
            <span className="text-sm text-slatewarm">Recipient: {activeRecipient || "None"}</span>
          </div>

          {warnings.length ? (
            <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              {warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}
