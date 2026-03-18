import { useEffect, useState } from "react";

const stages = [
  "Parsing resume",
  "Normalizing role and extracting keywords",
  "Searching public sources",
  "Filtering to US-based contacts",
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
    }, 1800);
    return () => window.clearInterval(timer);
  }, [active]);

  if (!active) {
    return null;
  }

  return (
    <section className="panel p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="font-display text-lg text-ink">{stages[index]}</p>
          <p className="mt-2 text-sm text-slatewarm">The request stays local except for public page fetches and your local Ollama instance.</p>
        </div>
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-spruce" />
      </div>
      <div className="mt-5 grid gap-2 md:grid-cols-5">
        {stages.map((stage, stageIndex) => (
          <div
            key={stage}
            className={`rounded-2xl px-3 py-3 text-sm transition ${
              stageIndex <= index ? "bg-spruce text-white" : "bg-slate-100 text-slatewarm"
            }`}
          >
            {stage}
          </div>
        ))}
      </div>
    </section>
  );
}

