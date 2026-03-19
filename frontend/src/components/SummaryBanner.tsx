import type { ContactSearchDebug } from "../types/api";
import { StatusBadge } from "./StatusBadge";

interface SummaryBannerProps {
  contactCount: number;
  verifiedEmailCount: number;
  warnings: string[];
  debug?: ContactSearchDebug;
}

export function SummaryBanner({ contactCount, verifiedEmailCount, warnings, debug }: SummaryBannerProps) {
  const warningTone: "warning" | "success" = warnings.length > 0 ? "warning" : "success";

  return (
    <section className="panel overflow-hidden px-5 py-5 md:px-6">
      <div className="grid gap-3 lg:grid-cols-[repeat(4,minmax(0,1fr))_1.2fr] lg:items-stretch">
        <Metric label="Contacts found" value={String(contactCount)} helper="Up to five ranked public contacts" />
        <Metric label="URLs considered" value={String(debug?.urls_considered ?? 0)} helper="Unique public results kept after dedupe" />
        <Metric label="Candidates kept" value={String(debug?.candidates_after_filtering ?? 0)} helper="Contacts that survived evidence and US filters" />
        <Metric label="Verified public emails" value={String(verifiedEmailCount)} helper={verifiedEmailCount ? "Ready for draft review" : "No public emails surfaced yet"} />
        <div className="rounded-[24px] border border-slate-200 bg-slate-950 px-4 py-4 text-white">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-200">Run summary</p>
              <p className="mt-2 text-sm leading-6 text-slate-200">
                {warnings[0] ?? "Public-source results and drafts are ready for review."}
              </p>
            </div>
            <StatusBadge label={warnings.length ? `${warnings.length} warning${warnings.length === 1 ? "" : "s"}` : "Ready"} tone={warningTone} />
          </div>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, helper }: { label: string; value: string; helper: string }) {
  return (
    <div className="rounded-[24px] border border-slate-200 bg-stone-50/85 px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-700">{helper}</p>
    </div>
  );
}
