const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

/** Anonymous per-browser id. Scopes the audit log, consents and "delete my data". */
function sessionId() {
  try {
    let id = localStorage.getItem("sessionId");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("sessionId", id);
    }
    return id;
  } catch {
    return "anonymous";
  }
}

const headers = () => ({ "Content-Type": "application/json", "X-Session-Id": sessionId() });

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}/api${path}`, { headers: headers(), ...options });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body) });

/**
 * Stream an answer over server-sent events. Calls onEvent({type, ...}) for each event:
 * `plan` and `step` (deep research only), then `sources`, `delta`, `done` (per
 * jurisdiction) and a final `end`.
 */
export async function streamAnswer({ query, jurisdiction, language, mode }, onEvent, signal) {
  const res = await fetch(`${BASE_URL}/api/ask/stream`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ query, jurisdiction, language, mode }),
    signal,
  });
  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) onEvent(JSON.parse(data));
    }
  }
}

export const api = {
  health: () => request("/health"),
  config: () => request("/config"),
  sources: () => request("/sources"),
  connectors: () => request("/connectors"),
  setConsent: (connector, granted) => post("/consents", { connector, granted }),
  escalate: (ticket) => post("/escalations", ticket),
  activity: () => request("/privacy/activity"),
  eraseActivity: () => request("/privacy/activity", { method: "DELETE" }),
  graph: () => request("/graph"),
  related: (nodeId) => request(`/graph/nodes/${encodeURIComponent(nodeId)}/related`),
  classify: (answers) => post("/classify", { answers }),
  absChecklist: (facts) => post("/abs-checklist", facts),
  tkdlPointer: (query) => request(`/tkdl-pointer?query=${encodeURIComponent(query)}`),
};
