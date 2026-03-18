import type { ReactNode } from "react";

interface SectionCardProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function SectionCard({ eyebrow, title, description, actions, children, className = "" }: SectionCardProps) {
  return (
    <section className={`panel overflow-hidden p-6 md:p-8 ${className}`.trim()}>
      <div className="flex flex-col gap-5 border-b border-slate-200/90 pb-6 md:flex-row md:items-start md:justify-between">
        <div className="space-y-3">
          {eyebrow ? (
            <span className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-800">
              {eyebrow}
            </span>
          ) : null}
          <div>
            <h2 className="text-[2rem] font-semibold leading-tight text-slate-950 md:text-[2.2rem]">{title}</h2>
            {description ? <p className="mt-3 max-w-3xl text-base leading-7 text-slate-700">{description}</p> : null}
          </div>
        </div>
        {actions ? <div className="shrink-0 md:pt-1">{actions}</div> : null}
      </div>
      <div className="pt-6">{children}</div>
    </section>
  );
}
