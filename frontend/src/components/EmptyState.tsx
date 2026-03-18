import { SectionCard } from "./SectionCard";
import { StatusBadge } from "./StatusBadge";

interface EmptyStateProps {
  warnings: string[];
}

export function EmptyState({ warnings }: EmptyStateProps) {
  return (
    <SectionCard
      eyebrow="Results"
      title="No contacts returned yet"
      description="This usually means public recruiter pages were sparse, location evidence was too weak, or search results were throttled."
      actions={<StatusBadge label={warnings.length ? `${warnings.length} warnings` : "Awaiting input"} tone={warnings.length ? "warning" : "neutral"} />}
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/80 p-5">
          <p className="text-sm font-semibold text-slate-900">What to try next</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
            <li>• Use a more specific company name and role title.</li>
            <li>• Paste a complete job description so the role can be normalized properly.</li>
            <li>• Upload a readable resume file in PDF, DOCX, TXT, or Markdown format.</li>
          </ul>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm font-semibold text-slate-900">Backend messages</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
            {warnings.length ? warnings.map((warning) => <li key={warning}>• {warning}</li>) : <li>• Run the main form to search public contacts and draft emails.</li>}
          </ul>
        </div>
      </div>
    </SectionCard>
  );
}
