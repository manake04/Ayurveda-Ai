import { Check, CircleSlash, Copy, Globe2, MapPin } from "lucide-react";
import { useState } from "react";
import { useT } from "../../lib/i18n.js";
import Markdown from "./Markdown.jsx";
import SourceList from "./SourceList.jsx";

const CONFIDENCE_STYLE = {
  high: "bg-primary-soft text-primary",
  medium: "bg-accent-soft text-accent",
  low: "bg-danger-soft text-danger",
};

export default function AnswerBlock({ turnId, block, showLabel }) {
  const t = useT();
  const [highlight, setHighlight] = useState(null);
  const [copied, setCopied] = useState(false);
  const idPrefix = `t${turnId}-${block.jurisdiction}`;
  const isIndia = block.jurisdiction === "india";

  const cite = (n) => {
    setHighlight(n);
    document.getElementById(`${idPrefix}-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    setTimeout(() => setHighlight((h) => (h === n ? null : h)), 1800);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(block.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <section className="animate-fade-up" aria-busy={block.status !== "done"}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {showLabel && (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
              isIndia ? "bg-primary-soft text-primary" : "bg-intl-soft text-intl"
            }`}
          >
            {isIndia ? <MapPin className="h-3.5 w-3.5" /> : <Globe2 className="h-3.5 w-3.5" />}
            {isIndia ? t.india : t.international}
          </span>
        )}
        {block.confidence && (
          <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${CONFIDENCE_STYLE[block.confidence]}`}>
            {t.confidence[block.confidence]}
          </span>
        )}
      </div>

      {block.status === "retrieving" && <AnswerSkeleton />}

      {block.abstained && block.status === "done" && (
        <div className="flex gap-3 rounded-xl border border-dashed border-line bg-sunken/60 p-4 text-sm leading-relaxed text-muted">
          <CircleSlash className="mt-0.5 h-4 w-4 shrink-0" />
          <p>{block.answer}</p>
        </div>
      )}

      {!block.abstained && block.status !== "retrieving" && (
        <>
          {block.answer ? (
            <div className="relative">
              <Markdown text={block.answer} onCite={cite} maxRef={block.citations.length} />
              {block.status === "writing" && (
                <span className="ml-0.5 inline-block h-4 w-[3px] translate-y-0.5 animate-blink rounded-sm bg-primary" />
              )}
            </div>
          ) : (
            block.status === "writing" && <AnswerSkeleton lines={2} />
          )}

          {block.status === "done" && (
            <div className="mt-2 flex items-center gap-3 text-xs text-faint">
              <button onClick={copy} className="inline-flex items-center gap-1 transition hover:text-ink">
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? t.copied : t.copy}
              </button>
              {block.generatedBy?.startsWith("extractive") && <span>· {t.quotedFromSources}</span>}
            </div>
          )}

          <SourceList
            citations={block.citations}
            related={block.related}
            highlight={highlight}
            idPrefix={idPrefix}
            answer={block.answer}
            done={block.status === "done"}
          />
        </>
      )}
    </section>
  );
}

function AnswerSkeleton({ lines = 3 }) {
  return (
    <div className="space-y-2.5 py-1" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="skeleton h-3.5" style={{ width: `${[92, 78, 64][i % 3]}%` }} />
      ))}
    </div>
  );
}
