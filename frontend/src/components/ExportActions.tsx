import { copyText, downloadCsv, downloadJson, combinedDraftText } from "../lib/utils";
import type { ContactCandidate, GeneratedEmailPayload } from "../types/api";

interface ExportActionsProps {
  contacts: ContactCandidate[];
  emails: GeneratedEmailPayload[];
}

export function ExportActions({ contacts, emails }: ExportActionsProps) {
  return (
    <div className="panel flex flex-wrap items-center gap-3 p-5">
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
  );
}

