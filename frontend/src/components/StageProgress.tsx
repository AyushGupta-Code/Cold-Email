const stages = [
  {
    title: "Parse inputs",
    description: "Resume text and job details are normalized before any search begins.",
  },
  {
    title: "Expand queries",
    description: "Heuristic recruiter queries run first, with Ollama expansion layered in when available.",
  },
  {
    title: "Search public sources",
    description: "The backend queries SearxNG when configured, then lightweight public HTML search fallbacks.",
  },
  {
    title: "Fetch public pages",
    description: "Promising public pages are fetched and compacted for evidence-backed extraction.",
  },
  {
    title: "Extract candidates",
    description: "Strict extraction pulls only supported names, titles, locations, and explicit emails.",
  },
  {
    title: "Validate US contacts",
    description: "Weak company matches, non-US signals, and unsupported fields are rejected.",
  },
  {
    title: "Rank results",
    description: "Heuristics and local reranking combine into the final top-contact list.",
  },
  {
    title: "Generate drafts",
    description: "After contacts are ranked, local Ollama draft generation runs for the review pane.",
  },
];

interface StageProgressProps {
  active: boolean;
}

export function StageProgress({ active }: StageProgressProps) {
  if (!active) return null;

  return (
    <section className="panel overflow-hidden p-0">
      <div className="flex flex-col gap-6 border-b border-slate-200/90 bg-stone-50/80 px-6 py-6 lg:flex-row lg:items-center lg:justify-between md:px-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700">Pipeline running</p>
          <h3 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">The current analysis run is executing the real backend pipeline</h3>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            This panel lists the real stages the backend runs. Per-stage telemetry is not streamed yet, so the UI no longer guesses a fake current step.
          </p>
          <div className="mt-4 h-2.5 max-w-xl overflow-hidden rounded-full bg-white">
            <div className="h-full w-full animate-pulse rounded-full bg-gradient-to-r from-amber-500 via-amber-400 to-teal-600" />
          </div>
        </div>
        <div className="shrink-0">
          <div className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800">
            {stages.length} backend stages
          </div>
        </div>
      </div>
      <div className="grid gap-3 px-6 py-6 sm:grid-cols-2 md:px-8 xl:grid-cols-4 2xl:grid-cols-7">
        {stages.map((stage, stageIndex) => (
          <div key={stage.title} className="rounded-[24px] border border-slate-200 bg-white px-4 py-4 text-sm text-slate-700 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Stage {stageIndex + 1}</p>
                <p className="mt-2 font-semibold leading-6 text-slate-950">{stage.title}</p>
              </div>
              <span className="mt-1 h-2.5 w-2.5 animate-pulse rounded-full bg-amber-500" />
            </div>
            <p className="mt-4 leading-6 text-slate-600">{stage.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
