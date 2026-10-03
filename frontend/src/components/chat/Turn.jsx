import { RotateCcw, Timer } from "lucide-react";
import { useT } from "../../lib/i18n.js";
import ErrorNote from "../ui/ErrorNote.jsx";
import Logo from "../ui/Logo.jsx";
import AnswerBlock from "./AnswerBlock.jsx";
import PlanPanel from "./PlanPanel.jsx";

export default function Turn({ turn, onRetry }) {
  const t = useT();
  const both = turn.order.length > 1;
  return (
    <article className="space-y-5">
      <div className="flex justify-end animate-fade-up">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-sunken px-4 py-2.5 text-[15px] leading-relaxed text-ink">
          {turn.query}
        </p>
      </div>

      <div className="flex gap-3 sm:gap-4">
        <Logo className="mt-0.5 hidden h-7 w-7 shrink-0 sm:block" />
        <div className="min-w-0 flex-1 space-y-8">
          {turn.plan && <PlanPanel plan={turn.plan} />}
          {turn.error ? (
            <ErrorNote
              action={
                <button onClick={() => onRetry(turn)} className="inline-flex items-center gap-1 font-medium underline-offset-2 hover:underline">
                  <RotateCcw className="h-3.5 w-3.5" />
                  {t.retry}
                </button>
              }
            >
              {turn.error.includes("fetch") ? t.backendDown : turn.error}
            </ErrorNote>
          ) : (
            turn.order.map((j, i) => (
              <div key={j} className={both && i > 0 ? "border-t border-line pt-8" : ""}>
                <AnswerBlock turnId={turn.id} block={turn.blocks[j]} query={turn.query} showLabel />
              </div>
            ))
          )}
          {turn.latencyMs != null && (
            <div className="flex items-center gap-1 text-[11px] text-faint">
              <Timer className="h-3 w-3" />
              {t.answeredIn} {(turn.latencyMs / 1000).toFixed(1)}s
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
