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
  const progress = ((index + 1) / stages.length) * 100;

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
    <section className="panel overflow-hidden p-0">
      <div className="flex flex-col gap-6 border-b border-slate-200/90 bg-stone-50/80 px-6 py-6 lg:flex-row lg:items-center lg:justify-between md:px-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700">In progress</p>
          <h3 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{stages[index]}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            The workflow remains local-first except for fetching public web pages and your local Ollama instance.
          </p>
          <div className="mt-4 h-2.5 max-w-xl overflow-hidden rounded-full bg-white">
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-500 via-amber-500 to-teal-600 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        <div className="shrink-0">
          <div className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800">
            {index + 1} / {stages.length} stages active
          </div>
        </div>
      </div>
      <div className="grid gap-3 px-6 py-6 sm:grid-cols-2 md:px-8 xl:grid-cols-5">
          {stages.map((stage, stageIndex) => {
            const isActive = stageIndex === index;
            const isComplete = stageIndex < index;
            return (
              <div
                key={stage}
                className={`rounded-[24px] border px-4 py-4 text-sm transition ${
                  isActive
                    ? "border-slate-950 bg-slate-950 text-white shadow-lg shadow-slate-950/10"
                    : isComplete
                      ? "border-teal-300 bg-teal-50 text-teal-900"
                      : "border-slate-200 bg-white text-slate-600"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isActive ? "text-amber-200" : isComplete ? "text-teal-700" : "text-slate-400"}`}>
                      Stage {stageIndex + 1}
                    </p>
                    <p className="mt-2 font-semibold leading-6">{stage}</p>
                  </div>
                  <span className={`mt-1 h-2.5 w-2.5 rounded-full ${isActive ? "bg-amber-400" : isComplete ? "bg-teal-500" : "bg-slate-200"}`} />
                </div>
                <div className={`mt-4 h-1.5 overflow-hidden rounded-full ${isActive ? "bg-white/15" : "bg-slate-100"}`}>
                  <div
                    className={`h-full rounded-full ${isActive ? "bg-amber-400" : isComplete ? "bg-teal-500" : "bg-slate-200"}`}
                    style={{ width: isComplete ? "100%" : isActive ? "65%" : "20%" }}
                  />
                </div>
              </div>
            );
          })}
      </div>
    </section>
  );
}
