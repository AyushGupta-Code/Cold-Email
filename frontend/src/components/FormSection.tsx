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
      description="Provide exactly four required inputs so the app can normalize the role, parse the resume, find public contacts, and draft local outreach emails."
      actions={<StatusBadge label="4 required inputs" tone="accent" />}
    >
      <form className="grid gap-6" onSubmit={onSubmit}>
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
          <label className="group mt-2 flex cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-slate-50 px-6 py-8 text-center transition hover:border-teal-300 hover:bg-teal-50/40">
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-xl shadow-sm">↑</span>
            <span className="mt-4 text-base font-semibold text-slate-900">{resumeFile ? resumeFile.name : "Choose a resume file"}</span>
            <span className="mt-2 max-w-md text-sm leading-6 text-slate-500">
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
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-700">
            {errors.map((error) => (
              <p key={error}>• {error}</p>
            ))}
          </div>
        ) : null}

        <div className="flex flex-col gap-3 rounded-3xl border border-slate-200 bg-slate-50/80 p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-900">Primary action</p>
            <p className="mt-1 text-sm text-slate-500">
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
    <label className="block text-sm font-medium text-slate-900">
      <div className="flex items-center justify-between gap-3">
        <span>{label}</span>
      </div>
      <p className="mt-1 text-sm font-normal leading-6 text-slate-500">{hint}</p>
      {children}
    </label>
  );
}
