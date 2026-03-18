import type { ChangeEvent, FormEvent } from "react";

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
    <section className="panel p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl text-ink">Analyze a target role</h2>
          <p className="mt-2 max-w-2xl text-sm text-slatewarm">
            The main workflow accepts exactly four inputs: company name, position, job description, and one resume file.
          </p>
        </div>
      </div>

      <form className="grid gap-5" onSubmit={onSubmit}>
        <label className="block text-sm font-medium text-ink">
          Company name
          <input className="field" value={companyName} onChange={(event) => onChange("companyName", event.target.value)} />
        </label>

        <label className="block text-sm font-medium text-ink">
          Position
          <input className="field" value={position} onChange={(event) => onChange("position", event.target.value)} />
        </label>

        <label className="block text-sm font-medium text-ink">
          Job description
          <textarea
            className="field min-h-40 resize-y"
            value={jobDescription}
            onChange={(event) => onChange("jobDescription", event.target.value)}
          />
        </label>

        <label className="block text-sm font-medium text-ink">
          Resume upload
          <input
            className="field cursor-pointer"
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={(event: ChangeEvent<HTMLInputElement>) => onFileChange(event.target.files?.[0] ?? null)}
          />
          <span className="mt-2 block text-xs text-slatewarm">{resumeFile ? resumeFile.name : "PDF, DOCX, or TXT"}</span>
        </label>

        {errors.length > 0 ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            {errors.map((error) => (
              <p key={error}>{error}</p>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <button className="button-primary" disabled={loading} type="submit">
            {loading ? "Working..." : "Find Contacts and Draft Emails"}
          </button>
          <p className="text-sm text-slatewarm">
            Public web only. If fewer than five valid contacts are found, the app returns fewer and explains why.
          </p>
        </div>
      </form>
    </section>
  );
}

