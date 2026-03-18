import type { ReactNode } from "react";

import { StatusBadge } from "./StatusBadge";

interface AppShellProps {
  children: ReactNode;
}

const steps = [
  "Step 1 · Role details",
  "Step 2 · Optional settings",
  "Step 3 · Contact review",
  "Step 4 · Draft actions",
];

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-app px-4 py-6 text-slate-900 sm:px-6 lg:px-8 lg:py-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="panel overflow-hidden px-6 py-6 md:px-8 md:py-8">
          <div className="grid gap-8 lg:grid-cols-[1.4fr_0.8fr] lg:items-start">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge label="Local-only workflow" tone="accent" />
                <StatusBadge label="Public source discovery" />
                <StatusBadge label="Manual review required" />
              </div>
              <p className="mt-5 text-sm font-semibold uppercase tracking-[0.28em] text-slate-500">Recruiter outreach workspace</p>
              <h1 className="mt-3 max-w-4xl text-4xl font-semibold tracking-tight text-slate-950 md:text-5xl">
                Find public recruiter contacts and draft tailored outreach with a cleaner, local-first workflow.
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
                Enter the four required inputs, optionally tune local settings, then review ranked public contacts and editable draft emails in one place.
              </p>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-slate-50/90 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Product guardrails</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
                <li>No fabricated email addresses or hidden enrichment.</li>
                <li>No authenticated scraping or cloud-only workflow assumptions.</li>
                <li>Detailed evidence and source links remain available on demand.</li>
                <li>SMTP sending stays optional and always requires explicit review.</li>
              </ul>
            </div>
          </div>
          <div className="mt-6 grid gap-2 md:grid-cols-4">
            {steps.map((step) => (
              <div key={step} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-600 shadow-sm">
                {step}
              </div>
            ))}
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
