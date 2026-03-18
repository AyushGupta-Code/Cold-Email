import { copyText, combinedDraftText, downloadCsv, downloadJson } from "../lib/utils";
import type { ContactCandidate, GeneratedEmailPayload } from "../types/api";

interface ExportActionsProps {
  contacts: ContactCandidate[];
  emails: GeneratedEmailPayload[];
}

export function ExportActions({ contacts, emails }: ExportActionsProps) {
  return (
    <div className="panel flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center md:justify-between md:px-6">
      <div>
        <p className="text-sm font-semibold text-slate-900">Exports and copy tools</p>
        <p className="text-sm text-slate-500">Keep the final review lightweight while retaining structured data when you need it.</p>
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
