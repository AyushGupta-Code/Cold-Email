import { useMemo, useState } from "react";

import { testOllama, testSmtp } from "../lib/api";
import type { SettingsFormValues } from "../types/api";
import { SectionCard } from "./SectionCard";
import { StatusBadge } from "./StatusBadge";

interface SettingsPanelProps {
  values: SettingsFormValues;
  onChange: <K extends keyof SettingsFormValues>(field: K, value: SettingsFormValues[K]) => void;
}

export function SettingsPanel({ values, onChange }: SettingsPanelProps) {
  const [ollamaStatus, setOllamaStatus] = useState<string>("");
  const [smtpStatus, setSmtpStatus] = useState<string>("");
  const [loading, setLoading] = useState<"" | "ollama" | "smtp">("");
  const [open, setOpen] = useState(false);
  const compactBaseUrl = values.ollamaBaseUrl.replace(/^https?:\/\//, "") || "Not set";

  const ollamaTone = useMemo(() => {
    if (!ollamaStatus) return "neutral" as const;
    return /ok|connected|ready|success/i.test(ollamaStatus) ? "success" : "warning";
  }, [ollamaStatus]);

  const smtpTone = useMemo(() => {
    if (!smtpStatus) return values.smtpEnabled ? "warning" as const : "neutral" as const;
    return /ok|connected|ready|success/i.test(smtpStatus) ? "success" : "warning";
  }, [smtpStatus, values.smtpEnabled]);

  async function handleTestOllama() {
    setLoading("ollama");
    setOllamaStatus("");
    try {
      const result = await testOllama(values.ollamaBaseUrl, values.ollamaModel);
      setOllamaStatus(result.message);
    } catch (error) {
      setOllamaStatus(error instanceof Error ? error.message : "Failed to test Ollama.");
    } finally {
      setLoading("");
    }
  }

  async function handleTestSmtp() {
    setLoading("smtp");
    setSmtpStatus("");
    try {
      const result = await testSmtp({
        host: values.smtpHost,
        port: values.smtpPort,
        username: values.smtpUsername,
        password: values.smtpPassword,
        senderEmail: values.smtpSenderEmail,
        useTls: values.smtpUseTls,
      });
      setSmtpStatus(result.message);
    } catch (error) {
      setSmtpStatus(error instanceof Error ? error.message : "Failed to test SMTP.");
    } finally {
      setLoading("");
    }
  }

  return (
    <SectionCard
      className="xl:sticky xl:top-6"
      eyebrow="Step 2"
      title="Local settings"
      description="Ollama powers draft generation. SMTP remains optional until you explicitly review and send a draft."
      actions={
        <div className="flex flex-wrap gap-2">
          <StatusBadge label={values.ollamaModel ? `Model: ${values.ollamaModel}` : "Ollama not set"} tone="accent" />
          <StatusBadge label={values.smtpEnabled ? "SMTP enabled" : "SMTP optional"} tone={values.smtpEnabled ? "warning" : "neutral"} />
        </div>
      }
    >
      <div className="space-y-4">
        <div className="rounded-[28px] border border-slate-200 bg-[linear-gradient(180deg,rgba(247,239,225,0.92),rgba(255,255,255,0.98))] p-5">
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
            <SummaryStat label="Local model" value={values.ollamaModel || "Not set"} helper="Draft generation" />
            <SummaryStat label="Ollama URL" value={compactBaseUrl} helper="Connection target" />
            <SummaryStat label="SMTP" value={values.smtpEnabled ? "Enabled" : "Disabled"} helper="Manual send support" />
          </div>
          <button
            className="mt-4 flex w-full items-center justify-between gap-4 rounded-[24px] border border-slate-200 bg-white/90 px-4 py-4 text-left transition hover:border-amber-300 hover:bg-amber-50/70"
            onClick={() => setOpen((current) => !current)}
            type="button"
          >
            <div>
              <p className="text-sm font-semibold text-slate-900">Connection settings</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">Expand to test your local Ollama instance and optional SMTP configuration.</p>
            </div>
            <span className="button-secondary !rounded-2xl">{open ? "Hide settings" : "Show settings"}</span>
          </button>
        </div>

        {open ? (
          <div className="grid gap-5 xl:grid-cols-1 2xl:grid-cols-2">
            <div className="rounded-[28px] border border-slate-200 bg-white/95 p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-950">Ollama</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-600">Required for generating local email drafts.</p>
                </div>
                <StatusBadge label={ollamaStatus || "Not tested yet"} tone={ollamaTone} />
              </div>
              <div className="mt-5 grid gap-4">
                <Input label="Base URL" value={values.ollamaBaseUrl} onChange={(value) => onChange("ollamaBaseUrl", value)} />
                <Input label="Model name" value={values.ollamaModel} onChange={(value) => onChange("ollamaModel", value)} />
                <Input label="Temperature" value={values.ollamaTemperature} onChange={(value) => onChange("ollamaTemperature", value)} />
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                <button className="button-secondary" disabled={loading === "ollama"} onClick={handleTestOllama} type="button">
                  {loading === "ollama" ? "Testing..." : "Test Ollama"}
                </button>
              </div>
            </div>

            <div className="rounded-[28px] border border-slate-200 bg-white/95 p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-slate-950">SMTP</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-600">Optional send support after manual review.</p>
                </div>
                <StatusBadge label={smtpStatus || (values.smtpEnabled ? "Enabled but untested" : "Disabled")} tone={smtpTone} />
              </div>

              <label className="mt-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-stone-50/80 px-4 py-3 text-sm font-medium text-slate-800">
                <input checked={values.smtpEnabled} onChange={(event) => onChange("smtpEnabled", event.target.checked)} type="checkbox" />
                Enable SMTP for manual sends
              </label>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <Input label="Host" value={values.smtpHost} onChange={(value) => onChange("smtpHost", value)} />
                <Input label="Port" value={values.smtpPort} onChange={(value) => onChange("smtpPort", value)} />
                <Input label="Username" value={values.smtpUsername} onChange={(value) => onChange("smtpUsername", value)} />
                <Input label="Password / app password" type="password" value={values.smtpPassword} onChange={(value) => onChange("smtpPassword", value)} />
                <div className="md:col-span-2">
                  <Input label="Sender email" value={values.smtpSenderEmail} onChange={(value) => onChange("smtpSenderEmail", value)} />
                </div>
              </div>

              <label className="mt-4 flex items-center gap-3 text-sm font-medium text-slate-800">
                <input checked={values.smtpUseTls} onChange={(event) => onChange("smtpUseTls", event.target.checked)} type="checkbox" />
                Use STARTTLS
              </label>

              <div className="mt-5 flex flex-wrap gap-3">
                <button className="button-secondary" disabled={loading === "smtp"} onClick={handleTestSmtp} type="button">
                  {loading === "smtp" ? "Testing..." : "Test SMTP"}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </SectionCard>
  );
}

function SummaryStat({ label, value, helper }: { label: string; value: string; helper: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white/85 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 line-clamp-2 text-sm font-semibold leading-6 text-slate-950">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-600">{helper}</p>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className="block text-sm font-medium text-slate-900">
      {label}
      <input className="field" type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
