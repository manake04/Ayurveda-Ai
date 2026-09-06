import { useState } from "react";
import { api } from "../api.js";
import JurisdictionAnswerBlock from "./JurisdictionAnswerBlock.jsx";
import AgenticTrace from "./AgenticTrace.jsx";

const SAMPLE_QUESTIONS = [
  "Can a classical Ayurvedic formulation be patented in India?",
  "What does the WIPO treaty on genetic resources require patent applicants to disclose?",
  "Do I need NBA approval before commercialising a product using an Indian medicinal plant?",
  "How can I register my Ayurvedic brand name in many countries at once?",
];

const AGENTIC_SAMPLE_QUESTIONS = [
  "I want to patent a new Ayurvedic formulation and also register its brand name, in both India and abroad — what do I need to do?",
  "My product uses a plant sourced in India and I want to export it — what IP and biodiversity approvals apply?",
];

export default function ChatWindow({ jurisdiction, language, uiStrings }) {
  const [query, setQuery] = useState("");
  const [agentic, setAgentic] = useState(false);
  // turns: { query, jurisdiction, mode, answers? , plan_summary?, steps?, sections? }[]
  const [turns, setTurns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function submit(q) {
    const text = (q ?? query).trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    try {
      if (agentic) {
        const res = await api.askAgentic(text, jurisdiction, language);
        setTurns((prev) => [
          ...prev,
          {
            query: text,
            jurisdiction,
            mode: "agentic",
            plan_summary: res.plan_summary,
            steps: res.steps,
            sections: res.sections,
          },
        ]);
      } else {
        const res = await api.ask(text, jurisdiction, language);
        setTurns((prev) => [...prev, { query: text, jurisdiction, mode: "standard", answers: res.answers }]);
      }
      setQuery("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const samples = agentic ? AGENTIC_SAMPLE_QUESTIONS : SAMPLE_QUESTIONS;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2 bg-white border border-stone-200 rounded-lg px-3 py-2">
        <div className="text-xs text-stone-500 max-w-md">
          {agentic
            ? "Agentic mode: plans multiple retrieval steps for compound, multi-jurisdiction or multi-regime questions, rule-based (no LLM key needed)."
            : "Standard mode: one grounded lookup per jurisdiction."}
        </div>
        <label className="flex items-center gap-2 text-xs font-medium text-stone-700 cursor-pointer select-none">
          <span>Agentic mode</span>
          <span
            role="switch"
            aria-checked={agentic}
            onClick={() => setAgentic((v) => !v)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
              agentic ? "bg-violet-600" : "bg-stone-300"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                agentic ? "translate-x-5" : "translate-x-1"
              }`}
            />
          </span>
        </label>
      </div>

      {turns.length === 0 && !loading && (
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <div className="text-sm text-stone-500 mb-2">Try a sample question:</div>
          <div className="flex flex-wrap gap-2">
            {samples.map((q) => (
              <button
                key={q}
                onClick={() => submit(q)}
                className="text-xs bg-stone-100 hover:bg-stone-200 text-stone-700 px-2.5 py-1.5 rounded-full"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-6">
        {turns.map((turn, i) => (
          <div key={i} className="space-y-3">
            <div className="flex items-center gap-2 ml-auto w-fit">
              {turn.mode === "agentic" && (
                <span className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-violet-600 text-white">
                  Agentic
                </span>
              )}
              <div className="max-w-xl bg-stone-900 text-white text-sm rounded-2xl rounded-br-sm px-4 py-2.5 w-fit">
                {turn.query}
              </div>
            </div>

            {turn.mode === "agentic" ? (
              <div className="space-y-3">
                <AgenticTrace planSummary={turn.plan_summary} steps={turn.steps} />
                {turn.sections.map((a, j) => (
                  <JurisdictionAnswerBlock key={j} answer={a} />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {turn.answers.map((a, j) => (
                  <JurisdictionAnswerBlock key={j} answer={a} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {loading && (
        <div className="text-sm text-stone-500 animate-pulse">
          {agentic ? "Planning steps and grounding each one…" : "Retrieving and grounding an answer…"}
        </div>
      )}
      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          Couldn't reach the backend: {error}. Is it running at the configured API URL?
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="sticky bottom-0 bg-stone-50 pt-2 flex gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={uiStrings.ask_placeholder}
          className="flex-1 border border-stone-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-stone-400"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-stone-900 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
