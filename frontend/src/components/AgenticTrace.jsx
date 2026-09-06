/** Renders the rule-based planner's reasoning trace for /ask/agentic -- how many
 * retrieval steps it decided to run, and why, before the grounded, cited answer
 * sections below. See backend/app/agent.py for the (no-LLM-required) planning logic
 * this is visualising; the shape is deliberately generic so a future LLM-based planner
 * could produce the same trace format. */
export default function AgenticTrace({ planSummary, steps }) {
  return (
    <div className="border border-violet-200 bg-violet-50/60 rounded-lg p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-violet-600 text-white">
          Agentic plan
        </span>
        <span className="text-xs text-violet-900">{planSummary}</span>
      </div>
      <ol className="space-y-1.5">
        {steps.map((s) => (
          <li key={s.step_index} className="flex items-start gap-2 text-xs text-violet-800">
            <span className="shrink-0 w-4 h-4 rounded-full bg-violet-600 text-white text-[10px] font-bold flex items-center justify-center mt-0.5">
              {s.step_index + 1}
            </span>
            <span>
              <strong className="font-semibold">
                {s.jurisdiction}
                {s.regime ? ` — ${s.regime}` : ""}:
              </strong>{" "}
              {s.reason}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
