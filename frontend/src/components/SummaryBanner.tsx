import { StatusBadge } from "./StatusBadge";

interface SummaryBannerProps {
  contactCount: number;
  verifiedEmailCount: number;
  warnings: string[];
}

export function SummaryBanner({ contactCount, verifiedEmailCount, warnings }: SummaryBannerProps) {
  const warningTone = warnings.length > 0 ? "warning" : "success" as const;

  return (
    <section className="panel px-5 py-4 md:px-6">
      <div className="grid gap-3 md:grid-cols-[repeat(3,minmax(0,1fr))_1.2fr] md:items-center">
        <Metric label="Contacts found" value={String(contactCount)} helper="Up to five ranked public contacts" />
        <Metric label="Verified public emails" value={String(verifiedEmailCount)} helper={verifiedEmailCount ? "Ready for draft review" : "No public emails surfaced yet"} />
        <Metric label="Warnings" value={String(warnings.length)} helper={warnings.length ? "Review before sending" : "No backend warnings reported"} />
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Run summary</p>
              <p className="mt-1 text-sm text-slate-600">
                {warnings[0] ?? "Public-source results and drafts are ready for review."}
              </p>
            </div>
            <StatusBadge label={warnings.length ? "Attention" : "Ready"} tone={warningTone} />
          </div>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, helper }: { label: string; value: string; helper: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{helper}</p>
    </div>
  );
}
