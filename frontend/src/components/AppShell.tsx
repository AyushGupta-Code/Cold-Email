import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen px-4 py-8 text-ink sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="panel overflow-hidden">
          <div className="grid gap-6 px-6 py-8 md:grid-cols-[1.3fr_0.7fr] md:px-8">
            <div>
              <p className="font-display text-sm uppercase tracking-[0.32em] text-spruce">Local-only recruiter outreach</p>
              <h1 className="mt-3 max-w-3xl font-display text-4xl leading-tight text-ink md:text-5xl">
                Public-contact discovery and personalized outreach drafts without cloud APIs.
              </h1>
              <p className="mt-4 max-w-2xl text-sm text-slatewarm md:text-base">
                This app finds public US-based recruiter-style contacts, surfaces source links, drafts local LLM emails,
                and keeps everything on your machine.
              </p>
            </div>
            <div className="rounded-[28px] border border-amber-200/80 bg-sand/90 p-5">
              <p className="font-display text-sm uppercase tracking-[0.28em] text-ember">Guardrails</p>
              <ul className="mt-4 space-y-3 text-sm text-slatewarm">
                <li>No fabricated email addresses.</li>
                <li>No authenticated scraping or LinkedIn login.</li>
                <li>No auto-send. Every message requires review and an explicit click.</li>
                <li>All settings and generated data remain local.</li>
              </ul>
            </div>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}

