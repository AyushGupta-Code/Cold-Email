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
    <div className="min-h-screen bg-app px-4 py-5 text-slate-900 sm:px-6 lg:px-8 lg:py-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 lg:gap-7">
        <header className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.82fr)]">
          <div className="relative overflow-hidden rounded-[36px] bg-slate-950 px-6 py-7 text-white shadow-panel md:px-8 md:py-8">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.28),transparent_34%),radial-gradient(circle_at_85%_12%,rgba(45,212,191,0.24),transparent_28%)]" />
            <div className="relative">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge label="Local-only workflow" tone="accent" />
                <StatusBadge label="Public source discovery" />
                <StatusBadge label="Manual review required" />
              </div>
              <p className="mt-6 text-sm font-semibold uppercase tracking-[0.28em] text-amber-200">Recruiter outreach workspace</p>
              <h1 className="mt-3 max-w-4xl text-4xl font-semibold tracking-tight text-white md:text-5xl">
                Find public recruiter contacts and draft tailored outreach in a review-first workspace.
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-slate-200">
                Enter the four required inputs, optionally tune local settings, then review ranked public contacts and editable draft emails without losing context.
              </p>
              <div className="mt-7 grid gap-3 sm:grid-cols-2">
                {steps.map((step, index) => (
                  <div key={step} className="rounded-[24px] border border-white/10 bg-white/8 px-4 py-4 backdrop-blur-sm">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-100">Stage {index + 1}</p>
                    <p className="mt-2 text-sm font-medium leading-6 text-white">{step}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="panel flex flex-col justify-between px-6 py-6 md:px-7 md:py-7">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-amber-700">Product guardrails</p>
              <h2 className="mt-3 text-3xl font-semibold leading-tight text-slate-950">Readable by default, explicit about risk.</h2>
              <p className="mt-3 text-base leading-7 text-slate-700">
                The interface keeps high-signal recruiter data, draft edits, and send controls visible while secondary evidence stays accessible on demand.
              </p>
              <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-700">
                <li>No fabricated email addresses or hidden enrichment.</li>
                <li>No authenticated scraping or cloud-only workflow assumptions.</li>
                <li>Detailed evidence and source links remain available on demand.</li>
                <li>SMTP sending stays optional and always requires explicit review.</li>
              </ul>
            </div>
            <div className="mt-6 rounded-[26px] border border-slate-200 bg-stone-50/85 px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">Workflow promise</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                Review contacts, inspect the source evidence, edit the draft, then decide whether anything should be copied or sent.
              </p>
            </div>
          </div>
        </header>
        <main className="space-y-6 lg:space-y-7">
          {children}
        </main>
      </div>
    </div>
  );
}
