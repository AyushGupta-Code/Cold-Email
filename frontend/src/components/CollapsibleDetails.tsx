import type { ReactNode } from "react";

interface CollapsibleDetailsProps {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function CollapsibleDetails({ title, summary, defaultOpen = false, children }: CollapsibleDetailsProps) {
  return (
    <details className="group rounded-2xl border border-slate-200 bg-slate-50/80 p-4" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          {summary ? <p className="mt-1 text-xs leading-5 text-slate-500">{summary}</p> : null}
        </div>
        <span className="text-xs font-medium text-slate-500 transition group-open:rotate-180">⌄</span>
      </summary>
      <div className="pt-4">{children}</div>
    </details>
  );
}
