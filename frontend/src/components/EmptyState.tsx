import type { ContactSearchDebug } from "../types/api";
import { SectionCard } from "./SectionCard";
import { StatusBadge } from "./StatusBadge";

interface EmptyStateProps {
  warnings: string[];
  debug?: ContactSearchDebug | null;
}

export function EmptyState({ warnings, debug }: EmptyStateProps) {
  const hasWarnings = warnings.length > 0;
  const hasDebug = Boolean(debug && (debug.urls_considered || debug.candidates_extracted || debug.candidates_after_filtering));

  return (
    <SectionCard
      eyebrow="Results"
      title={hasWarnings ? "No contacts returned yet" : "Run the workflow to populate results"}
      description={
        hasWarnings
          ? "This usually means search retrieval was thin, evidence was too weak, or the remaining contacts failed company, title, or US validation."
          : "Once the form is submitted, contacts, evidence, draft emails, and export actions will appear here."
      }
      actions={<StatusBadge label={hasWarnings ? `${warnings.length} warnings` : "Awaiting input"} tone={hasWarnings ? "warning" : "neutral"} />}
    >
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-[28px] border border-dashed border-slate-400 bg-[linear-gradient(180deg,rgba(247,239,225,0.88),rgba(255,255,255,0.96))] p-5">
          <p className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-800">
            Workflow preview
          </p>
          <h3 className="mt-4 text-2xl font-semibold text-slate-950">
            {hasWarnings ? "Tighten the inputs and rerun the search." : "Contacts, evidence, and drafts appear here after the first run."}
          </h3>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <PreviewTile title="Contacts" description="Ranked public recruiter profiles." />
            <PreviewTile title="Evidence" description="Source links and score rationale." />
            <PreviewTile title="Drafts" description="Editable outreach emails and send controls." />
          </div>
          {hasDebug ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <PreviewTile title="URLs considered" description={String(debug?.urls_considered ?? 0)} />
              <PreviewTile title="Candidates extracted" description={String(debug?.candidates_extracted ?? 0)} />
              <PreviewTile title="Candidates kept" description={String(debug?.candidates_after_filtering ?? 0)} />
            </div>
          ) : null}
        </div>
        <div className="rounded-[24px] border border-slate-200 bg-white/95 p-5">
          <p className="text-sm font-semibold text-slate-950">{hasWarnings ? "Backend messages" : "What appears after a run"}</p>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
            {warnings.length ? (
              warnings.map((warning) => <li key={warning}>• {warning}</li>)
            ) : (
              <>
                <li>• Use the main form to search public contacts and generate draft emails.</li>
                <li>• Review the ranked results, evidence, and editable drafts before copying or sending anything.</li>
              </>
            )}
          </ul>
        </div>
      </div>
    </SectionCard>
  );
}

function PreviewTile({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white/80 px-4 py-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
    </div>
  );
}
