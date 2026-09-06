import { useState } from "react";
import { api } from "../api.js";

const FIELDS = [
  { key: "uses_biological_material", label: "Uses biological material (plant, microbial or animal-derived) in the formulation" },
  { key: "sourced_from_india", label: "That biological material is sourced from India" },
  { key: "ip_or_commercialisation_sought", label: "You plan to seek IP rights and/or commercialise it" },
  { key: "user_is_registered_ayush_practitioner", label: "You are a registered AYUSH practitioner" },
  { key: "knowledge_is_codified_traditional_knowledge", label: "The knowledge used is codified traditional knowledge (from a recognised classical text)" },
  { key: "exporting_or_partnering_abroad", label: "You plan to export, or partner with an entity, abroad" },
];

const DEFAULT_STATE = Object.fromEntries(FIELDS.map((f) => [f.key, false]));

export default function ABSHelper() {
  const [state, setState] = useState(DEFAULT_STATE);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.absHelper(state);
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
        <div className="text-xs font-semibold text-stone-400 uppercase tracking-wide mb-1">Access &amp; Benefit-Sharing helper</div>
        <p className="text-sm text-stone-600">
          Answer what applies to your situation, then generate a guided checklist of which ABS duties likely apply.
        </p>
      </div>

      <div className="space-y-2">
        {FIELDS.map((f) => (
          <label key={f.key} className="flex items-start gap-2 text-sm text-stone-800 cursor-pointer">
            <input
              type="checkbox"
              checked={state[f.key]}
              onChange={(e) => setState((s) => ({ ...s, [f.key]: e.target.checked }))}
              className="mt-1"
            />
            {f.label}
          </label>
        ))}
      </div>

      <button
        onClick={run}
        disabled={loading}
        className="bg-stone-900 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
      >
        {loading ? "Checking…" : "Generate checklist"}
      </button>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          Couldn't reach the backend: {error}.
        </div>
      )}

      {result && (
        <div className="space-y-2 pt-2 border-t border-stone-100">
          {result.checklist.map((item, i) => (
            <div
              key={i}
              className={`rounded-lg p-3 text-sm border ${
                item.applies ? "border-amber-300 bg-amber-50" : "border-stone-200 bg-stone-50 text-stone-500"
              }`}
            >
              <div className="font-medium flex items-center gap-2">
                <span>{item.applies ? "⚠️" : "—"}</span> {item.step}
              </div>
              <p className="mt-1">{item.detail}</p>
              <div className="flex gap-1.5 mt-2">
                {item.citation_ids.map((id) => (
                  <span key={id} className="text-xs bg-white border border-stone-200 px-1.5 py-0.5 rounded font-mono">
                    {id}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
