const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),
  corpusStats: () => request("/corpus/stats"),
  ask: (query, jurisdiction, language) =>
    request("/ask", {
      method: "POST",
      body: JSON.stringify({ query, jurisdiction, language }),
    }),
  askAgentic: (query, jurisdiction, language) =>
    request("/ask/agentic", {
      method: "POST",
      body: JSON.stringify({ query, jurisdiction, language }),
    }),
  graphExport: () => request("/graph/export"),
  graphRelated: (nodeId, hops = 1) => request(`/graph/node/${encodeURIComponent(nodeId)}/related?hops=${hops}`),
  graphPath: (source, target) =>
    request(`/graph/path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`),
  classifyStep: (answers) =>
    request("/classify", {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),
  absHelper: (payload) =>
    request("/abs-helper", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  tkdlPointer: (query) => request(`/tkdl-pointer?query=${encodeURIComponent(query)}`),
  connectorConsent: (connector_name, granted) =>
    request("/connectors/consent", {
      method: "POST",
      body: JSON.stringify({ connector_name, granted }),
    }),
  auditRecent: (limit = 10) => request(`/audit/recent?limit=${limit}`),
};

export { BASE_URL };
