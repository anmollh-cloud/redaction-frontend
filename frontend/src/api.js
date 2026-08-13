export const API_BASE =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

async function parseError(response) {
  try {
    const body = await response.json();
    return body.detail || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function redactText(text, entities) {
  const res = await fetch(`${API_BASE}/api/redact/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, entities }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function redactFile({ file, entities, useAzure, azureEndpoint, azureKey }) {
  const form = new FormData();
  form.append("file", file);
  if (entities && entities.length) form.append("entities", entities.join(","));
  form.append("use_azure", useAzure ? "true" : "false");
  if (azureEndpoint) form.append("azure_endpoint", azureEndpoint);
  if (azureKey) form.append("azure_key", azureKey);

  const res = await fetch(`${API_BASE}/api/redact/file`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchEntityCatalog() {
  const res = await fetch(`${API_BASE}/api/entities`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
