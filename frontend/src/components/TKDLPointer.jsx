import { useState } from "react";
import { api } from "../api.js";

export default function TKDLPointer() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.tkdlPointer(query.trim());
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-5 max-w-2xl space-y-4">
      <div>
        <div className="text-xs font-semibold text-stone-400 uppercase tracking-wide mb-1">
          TKDL / prior-art pointer
        </div>
        <p className="text-sm text-stone-600">
          Describe your formulation or ingredient to get pointed to TKDL and complementary public prior-art
          search tools (TKDL itself is not publicly queryable -- see the guidance below).
        </p>
      </div>

      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. ashwagandha churna for stress"
          className="flex-1 border border-stone-300 rounded-lg px-3 py-2 text-sm"
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <button
          onClick={run}
          disabled={loading}
          className="bg-stone-900 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {loading ? "…" : "Search"}
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          Couldn't reach the backend: {error}.
        </div>
      )}

      {result && (
        <div className="space-y-3 pt-2 border-t border-stone-100">
          <p className="text-sm text-stone-800 leading-relaxed">{result.guidance}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {result.search_links.map((l) => (
              <a
                key={l.url}
                href={l.url}
                target="_blank"
                rel="noreferrer"
                className="block border border-stone-200 rounded-lg p-3 hover:border-stone-400 text-sm"
              >
                <div className="font-medium text-stone-900">{l.name}</div>
                <div className="text-xs text-stone-500 mt-1">{l.note}</div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
