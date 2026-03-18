import { copyText, combinedDraftText, downloadCsv, downloadJson } from "../lib/utils";
import type { ContactCandidate, GeneratedEmailPayload } from "../types/api";

interface ExportActionsProps {
  contacts: ContactCandidate[];
  emails: GeneratedEmailPayload[];
}

export function ExportActions({ contacts, emails }: ExportActionsProps) {
  return (
    <div className="panel flex flex-col gap-4 px-5 py-5 md:flex-row md:items-center md:justify-between md:px-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">Output tools</p>
        <p className="mt-2 text-lg font-semibold text-slate-950">Export or copy the reviewed run.</p>
        <p className="mt-1 text-sm leading-6 text-slate-700">Keep the final review lightweight while retaining structured data when you need it.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button className="button-secondary" onClick={() => downloadJson("contacts-and-drafts.json", { contacts, emails })} type="button">
          Export JSON
        </button>
        <button className="button-secondary" onClick={() => downloadCsv("contacts-and-drafts.csv", contacts, emails)} type="button">
          Export CSV
        </button>
        <button className="button-secondary" onClick={() => copyText(combinedDraftText(contacts, emails))} type="button">
          Copy all drafts
        </button>
      </div>
    </div>
  );
}
