import { CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { useT } from "../../lib/i18n.js";

/** Deep research: the sub-questions being searched, ticked off as each finishes. */
export default function PlanPanel({ plan }) {
  const t = useT();
  const done = plan.every((s) => s.done);
  return (
    <div className="animate-fade-up rounded-xl border border-accent/30 bg-accent-soft/40 p-3.5">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-accent">
        <Sparkles className="h-3.5 w-3.5" />
        {t.researching} {plan.length} {t.subQuestions}
      </div>
      <ol className="space-y-1.5">
        {plan.map((step, i) => {
          const found = step.found ? Object.values(step.found).reduce((a, b) => a + b, 0) : null;
          return (
            <li key={i} className="flex items-start gap-2 text-sm leading-snug">
              {step.done || done ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              ) : (
                <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-faint" />
              )}
              <span className={step.done || done ? "text-ink" : "text-muted"}>
                {step.question}
                {found != null && (
                  <span className="ml-1.5 whitespace-nowrap text-xs text-faint">
                    · {found} {t.found}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
