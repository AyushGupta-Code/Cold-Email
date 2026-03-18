import type { ContactCandidate, GeneratedEmailPayload, RuntimeSettingsPayload, SettingsFormValues } from "../types/api";

export async function copyText(value: string) {
  await navigator.clipboard.writeText(value);
}

export function toRuntimeSettingsPayload(values: SettingsFormValues): RuntimeSettingsPayload {
  return {
    ollama_base_url: values.ollamaBaseUrl.trim() || undefined,
    ollama_model: values.ollamaModel.trim() || undefined,
    ollama_temperature: values.ollamaTemperature ? Number(values.ollamaTemperature) : undefined,
    smtp_enabled: values.smtpEnabled,
    smtp_host: values.smtpHost.trim() || undefined,
    smtp_port: values.smtpPort ? Number(values.smtpPort) : undefined,
    smtp_username: values.smtpUsername.trim() || undefined,
    smtp_password: values.smtpPassword || undefined,
    smtp_sender_email: values.smtpSenderEmail.trim() || undefined,
    smtp_use_tls: values.smtpUseTls,
  };
}

export function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  triggerDownload(filename, url);
}

export function downloadCsv(filename: string, contacts: ContactCandidate[], emails: GeneratedEmailPayload[]) {
  const emailMap = new Map(emails.map((item) => [item.contact_id, item]));
  const rows = [
    [
      "name",
      "title",
      "company",
      "location",
      "profile_url",
      "public_email",
      "score",
      "subject",
      "body",
      "sources",
    ],
    ...contacts.map((contact) => {
      const email = emailMap.get(contact.id);
      return [
        contact.full_name,
        contact.title,
        contact.company,
        contact.location,
        contact.profile_url,
        contact.public_email ?? "",
        String(contact.score),
        email?.subject ?? "",
        email?.body ?? "",
        contact.source_urls.join(" | "),
      ];
    }),
  ];
  const csv = rows
    .map((row) => row.map((value) => `"${value.split('"').join('""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  triggerDownload(filename, url);
}

export function combinedDraftText(contacts: ContactCandidate[], emails: GeneratedEmailPayload[]) {
  const emailMap = new Map(emails.map((item) => [item.contact_id, item]));
  return contacts
    .map((contact) => {
      const email = emailMap.get(contact.id);
      return [
        `${contact.full_name} | ${contact.title} | ${contact.company}`,
        `Subject: ${email?.subject ?? ""}`,
        email?.body ?? "",
      ].join("\n");
    })
    .join("\n\n---\n\n");
}

function triggerDownload(filename: string, url: string) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
