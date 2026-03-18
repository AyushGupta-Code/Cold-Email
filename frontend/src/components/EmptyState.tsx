import { SectionCard } from "./SectionCard";
import { StatusBadge } from "./StatusBadge";

interface EmptyStateProps {
  warnings: string[];
}

export function EmptyState({ warnings }: EmptyStateProps) {
  const hasWarnings = warnings.length > 0;

  return (
    <SectionCard
      eyebrow="Results"
      title={hasWarnings ? "No contacts returned yet" : "Run the workflow to populate results"}
      description={
        hasWarnings
          ? "This usually means public recruiter pages were sparse, location evidence was too weak, or search results were throttled."
          : "Once the form is submitted, contacts, evidence, draft emails, and export actions will appear here."
      }
      actions={<StatusBadge label={hasWarnings ? `${warnings.length} warnings` : "Awaiting input"} tone={hasWarnings ? "warning" : "neutral"} />}
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-[24px] border border-dashed border-slate-400 bg-stone-50/80 p-5">
          <p className="text-sm font-semibold text-slate-950">{hasWarnings ? "What to try next" : "Before you run it"}</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
            <li>• Use a more specific company name and role title.</li>
            <li>• Paste a complete job description so the role can be normalized properly.</li>
            <li>• Upload a readable resume file in PDF, DOCX, TXT, or Markdown format.</li>
          </ul>
        </div>
        <div className="rounded-[24px] border border-slate-200 bg-white/95 p-5">
          <p className="text-sm font-semibold text-slate-950">{hasWarnings ? "Backend messages" : "What appears after a run"}</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
            {warnings.length ? warnings.map((warning) => <li key={warning}>• {warning}</li>) : <li>• Run the main form to search public contacts and draft emails.</li>}
          </ul>
        </div>
      </div>
    </SectionCard>
  );
}
