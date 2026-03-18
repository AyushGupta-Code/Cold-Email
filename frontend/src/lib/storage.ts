import type { SettingsFormValues } from "../types/api";

const STORAGE_KEY = "local-recruiter-outreach:settings";

export const defaultSettings: SettingsFormValues = {
  ollamaBaseUrl: "http://localhost:11434",
  ollamaModel: "mistral",
  ollamaTemperature: "0.2",
  smtpEnabled: false,
  smtpHost: "",
  smtpPort: "587",
  smtpUsername: "",
  smtpPassword: "",
  smtpSenderEmail: "",
  smtpUseTls: true,
};

export function loadSettings(): SettingsFormValues {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return defaultSettings;
  }
  try {
    return { ...defaultSettings, ...(JSON.parse(raw) as Partial<SettingsFormValues>) };
  } catch {
    return defaultSettings;
  }
}

export function saveSettings(values: SettingsFormValues) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(values));
}

