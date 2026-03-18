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
    <section className={`panel p-6 md:p-8 ${className}`.trim()}>
      <div className="flex flex-col gap-4 border-b border-slate-200/80 pb-5 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          {eyebrow ? <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">{eyebrow}</p> : null}
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-950 md:text-[1.75rem]">{title}</h2>
            {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{description}</p> : null}
          </div>
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
      <div className="pt-6">{children}</div>
    </section>
  );
}
