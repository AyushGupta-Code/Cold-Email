import { useState } from "react";

import { testOllama, testSmtp } from "../lib/api";
import type { SettingsFormValues } from "../types/api";

interface SettingsPanelProps {
  values: SettingsFormValues;
  onChange: <K extends keyof SettingsFormValues>(field: K, value: SettingsFormValues[K]) => void;
}

export function SettingsPanel({ values, onChange }: SettingsPanelProps) {
  const [ollamaStatus, setOllamaStatus] = useState<string>("");
  const [smtpStatus, setSmtpStatus] = useState<string>("");
  const [loading, setLoading] = useState<"" | "ollama" | "smtp">("");

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
    <section className="panel p-6 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl text-ink">Settings</h2>
          <p className="mt-2 text-sm text-slatewarm">
            Ollama is required for draft generation. SMTP is optional and only used after manual review.
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slatewarm">
          Local only
        </span>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-[28px] border border-slate-200 p-5">
          <h3 className="font-display text-lg">Ollama</h3>
          <label className="mt-4 block text-sm font-medium">
            Ollama base URL
            <input className="field" value={values.ollamaBaseUrl} onChange={(event) => onChange("ollamaBaseUrl", event.target.value)} />
          </label>
          <label className="mt-4 block text-sm font-medium">
            Ollama model name
            <input className="field" value={values.ollamaModel} onChange={(event) => onChange("ollamaModel", event.target.value)} />
          </label>
          <label className="mt-4 block text-sm font-medium">
            Temperature
            <input className="field" value={values.ollamaTemperature} onChange={(event) => onChange("ollamaTemperature", event.target.value)} />
          </label>
          <div className="mt-4 flex items-center gap-3">
            <button className="button-secondary" disabled={loading === "ollama"} onClick={handleTestOllama} type="button">
              {loading === "ollama" ? "Testing..." : "Test connection"}
            </button>
            {ollamaStatus ? <span className="text-sm text-slatewarm">{ollamaStatus}</span> : null}
          </div>
        </div>

        <div className="rounded-[28px] border border-slate-200 p-5">
          <div className="flex items-center justify-between gap-4">
            <h3 className="font-display text-lg">SMTP</h3>
            <label className="flex items-center gap-2 text-sm font-medium">
              <input
                checked={values.smtpEnabled}
                onChange={(event) => onChange("smtpEnabled", event.target.checked)}
                type="checkbox"
              />
              Optional send support
            </label>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="block text-sm font-medium">
              Host
              <input className="field" value={values.smtpHost} onChange={(event) => onChange("smtpHost", event.target.value)} />
            </label>
            <label className="block text-sm font-medium">
              Port
              <input className="field" value={values.smtpPort} onChange={(event) => onChange("smtpPort", event.target.value)} />
            </label>
            <label className="block text-sm font-medium">
              Username
              <input className="field" value={values.smtpUsername} onChange={(event) => onChange("smtpUsername", event.target.value)} />
            </label>
            <label className="block text-sm font-medium">
              Password / app password
              <input
                className="field"
                type="password"
                value={values.smtpPassword}
                onChange={(event) => onChange("smtpPassword", event.target.value)}
              />
            </label>
            <label className="block text-sm font-medium md:col-span-2">
              Sender email
              <input
                className="field"
                value={values.smtpSenderEmail}
                onChange={(event) => onChange("smtpSenderEmail", event.target.value)}
              />
            </label>
          </div>
          <label className="mt-4 flex items-center gap-2 text-sm font-medium">
            <input checked={values.smtpUseTls} onChange={(event) => onChange("smtpUseTls", event.target.checked)} type="checkbox" />
            Use STARTTLS
          </label>
          <div className="mt-4 flex items-center gap-3">
            <button className="button-secondary" disabled={loading === "smtp"} onClick={handleTestSmtp} type="button">
              {loading === "smtp" ? "Testing..." : "Test connection"}
            </button>
            {smtpStatus ? <span className="text-sm text-slatewarm">{smtpStatus}</span> : null}
          </div>
        </div>
      </div>
    </section>
  );
}

