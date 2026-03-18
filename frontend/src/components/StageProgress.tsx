import { useEffect, useState } from "react";

const stages = [
  "Parsing resume",
  "Normalizing role",
  "Searching public sources",
  "Filtering contacts",
  "Drafting emails with Ollama",
];

interface StageProgressProps {
  active: boolean;
}

export function StageProgress({ active }: StageProgressProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % stages.length);
    }, 1600);
    return () => window.clearInterval(timer);
  }, [active]);

  if (!active) return null;

  return (
    <section className="panel p-6 md:p-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">In progress</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{stages[index]}</h3>
          <p className="mt-2 text-sm text-slate-500">
            The workflow remains local-first except for fetching public web pages and your local Ollama instance.
          </p>
        </div>
        <div className="grid w-full gap-3 sm:grid-cols-2 lg:max-w-xl lg:grid-cols-5">
          {stages.map((stage, stageIndex) => {
            const isActive = stageIndex === index;
            const isComplete = stageIndex < index;
            return (
              <div
                key={stage}
                className={`rounded-2xl border px-4 py-3 text-sm transition ${
                  isActive
                    ? "border-teal-200 bg-teal-50 text-teal-700"
                    : isComplete
                      ? "border-slate-200 bg-white text-slate-700"
                      : "border-slate-200 bg-slate-50 text-slate-400"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span>{stage}</span>
                  <span className={`h-2.5 w-2.5 rounded-full ${isActive ? "bg-teal-500" : isComplete ? "bg-slate-400" : "bg-slate-200"}`} />
                </div>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/80">
                  <div className={`h-full rounded-full ${isActive || isComplete ? "bg-teal-500" : "bg-slate-200"}`} style={{ width: isComplete ? "100%" : isActive ? "65%" : "20%" }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
