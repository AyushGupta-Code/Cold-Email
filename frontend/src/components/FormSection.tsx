import type { ChangeEvent, FormEvent, ReactNode } from "react";

import { SectionCard } from "./SectionCard";
import { StatusBadge } from "./StatusBadge";

interface FormSectionProps {
  companyName: string;
  position: string;
  jobDescription: string;
  resumeFile: File | null;
  errors: string[];
  loading: boolean;
  onChange: (field: "companyName" | "position" | "jobDescription", value: string) => void;
  onFileChange: (file: File | null) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function FormSection(props: FormSectionProps) {
  const { companyName, position, jobDescription, resumeFile, errors, loading, onChange, onFileChange, onSubmit } = props;

  return (
    <SectionCard
      eyebrow="Step 1"
      title="Enter the role details"
      description="Provide the four required inputs so the app can normalize the role, parse the resume, find public contacts, and draft local outreach emails with better source grounding."
      actions={<StatusBadge label="4 required inputs" tone="accent" />}
    >
      <form className="grid gap-7" onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <QuickInput step="01" label="Company" detail="Target organization" />
          <QuickInput step="02" label="Position" detail="Role title and scope" />
          <QuickInput step="03" label="Job description" detail="Source material for ranking" />
          <QuickInput step="04" label="Resume" detail="Candidate context" />
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="Company name" hint="Target company for recruiter discovery.">
            <input className="field" placeholder="Acme Labs" value={companyName} onChange={(event) => onChange("companyName", event.target.value)} />
          </Field>
          <Field label="Position" hint="Role title used for matching and ranking.">
            <input className="field" placeholder="Product Designer" value={position} onChange={(event) => onChange("position", event.target.value)} />
          </Field>
        </div>

        <Field label="Job description" hint="Paste the full posting or the most relevant parts. A larger, readable description improves the downstream ranking.">
          <textarea
            className="field min-h-[220px] resize-y"
            placeholder="Paste the job description here..."
            value={jobDescription}
            onChange={(event) => onChange("jobDescription", event.target.value)}
          />
        </Field>

        <Field label="Resume upload" hint="Accepted formats: PDF, DOCX, TXT, or Markdown.">
          <label className="group mt-2 flex cursor-pointer flex-col items-center justify-center rounded-[28px] border border-dashed border-slate-400/80 bg-stone-50/90 px-6 py-9 text-center shadow-inner transition hover:border-amber-400 hover:bg-amber-50/60">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-xl shadow-sm transition group-hover:-translate-y-0.5">↑</span>
            <span className="mt-4 text-base font-semibold text-slate-900">{resumeFile ? resumeFile.name : "Choose a resume file"}</span>
            <span className="mt-2 max-w-md text-sm leading-6 text-slate-600">
              {resumeFile ? "Selected and ready for parsing." : "Drop a file here or click to browse. Keep this input focused on one resume only."}
            </span>
            <input
              className="sr-only"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(event: ChangeEvent<HTMLInputElement>) => onFileChange(event.target.files?.[0] ?? null)}
            />
          </label>
        </Field>

        {errors.length > 0 ? (
          <div className="rounded-[24px] border border-rose-300 bg-rose-50 px-4 py-4 text-sm leading-6 text-rose-800">
            {errors.map((error) => (
              <p key={error}>• {error}</p>
            ))}
          </div>
        ) : null}

        <div className="grid gap-4 rounded-[28px] border border-slate-200 bg-[linear-gradient(135deg,rgba(255,251,235,0.92),rgba(255,255,255,0.98))] p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-700">Primary action</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">Find contacts and generate editable draft emails.</p>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              Public web only. If fewer than five valid contacts are found, the app returns fewer and explains why.
            </p>
          </div>
          <button className="button-primary min-w-[260px]" disabled={loading} type="submit">
            {loading ? "Finding contacts and drafting..." : "Find Contacts and Draft Emails"}
          </button>
        </div>
      </form>
    </SectionCard>
  );
}

function Field({ label, hint, children }: { label: string; hint: string; children: ReactNode }) {
  return (
    <label className="block">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-slate-950">{label}</span>
      </div>
      <p className="mt-1 text-sm leading-6 text-slate-600">{hint}</p>
      {children}
    </label>
  );
}

function QuickInput({ step, label, detail }: { step: string; label: string; detail: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-stone-50/85 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-700">{step}</p>
      <p className="mt-2 text-sm font-semibold text-slate-950">{label}</p>
      <p className="mt-1 text-sm leading-6 text-slate-600">{detail}</p>
    </div>
  );
}
