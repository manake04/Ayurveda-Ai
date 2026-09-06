import { useState } from "react";

export default function CitationCard({ citation }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-stone-200 rounded-lg p-3 hover:border-stone-400 hover:shadow-sm transition-all bg-white">
      <a href={citation.source_url} target="_blank" rel="noreferrer" className="block">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-sm font-semibold text-stone-900">{citation.title}</div>
            <div className="text-xs text-stone-500 mt-0.5">
              {citation.instrument} &middot; {citation.citation}
            </div>
          </div>
          <span className="shrink-0 text-[10px] uppercase tracking-wide font-semibold px-1.5 py-0.5 rounded bg-stone-100 text-stone-600">
            {citation.jurisdiction}
          </span>
        </div>
        <div className="text-xs text-stone-400 mt-2 flex items-center justify-between">
          <span>{citation.source_name}</span>
          <span>verified {citation.last_verified}</span>
        </div>
      </a>

      {citation.full_text_excerpt && (
        <div className="mt-2 pt-2 border-t border-stone-100">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-[11px] font-semibold text-stone-500 hover:text-stone-800 uppercase tracking-wide"
          >
            {expanded ? "Hide" : "Show"} verbatim text
          </button>
          {expanded && (
            <blockquote className="mt-1.5 text-xs text-stone-600 italic border-l-2 border-stone-300 pl-2 whitespace-pre-line">
              &ldquo;{citation.full_text_excerpt}&rdquo;
            </blockquote>
          )}
        </div>
      )}
    </div>
  );
}
