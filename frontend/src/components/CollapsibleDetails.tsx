import type { ReactNode } from "react";

interface CollapsibleDetailsProps {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function CollapsibleDetails({ title, summary, defaultOpen = false, children }: CollapsibleDetailsProps) {
  return (
    <details className="group rounded-[24px] border border-slate-200 bg-stone-50/80 p-4 shadow-sm" open={defaultOpen}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          {summary ? <p className="mt-1 text-sm leading-6 text-slate-600">{summary}</p> : null}
        </div>
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 bg-white text-sm text-slate-600 transition group-open:rotate-180">
          ⌄
        </span>
      </summary>
      <div className="pt-4">{children}</div>
    </details>
  );
}
