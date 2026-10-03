import { ChevronDown, ExternalLink, GitBranch } from "lucide-react";
import { useState } from "react";
import { useT } from "../../lib/i18n.js";

export function SourceCard({ c, highlighted, id }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <li
      id={id}
      className={`rounded-xl border bg-surface p-3 transition ${highlighted ? "border-primary ring-2 ring-primary/20" : "border-line"}`}
    >
      <div className="flex gap-3">
        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-sunken font-mono text-[11px] text-muted">
          {c.ref}
        </span>
        <div className="min-w-0 flex-1">
          <a
            href={c.source_url}
            target="_blank"
            rel="noreferrer"
            className="group inline-flex items-start gap-1 text-sm font-medium leading-snug text-ink hover:text-primary"
          >
            {c.title}
            <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-40 group-hover:opacity-100" />
          </a>
          <div className="mt-0.5 text-xs text-muted">
            {c.instrument} · <span className="font-medium">{c.citation}</span>
          </div>
          <div className="mt-1 text-[11px] text-faint">
            {c.source_name} · {t.verified} {c.last_verified}
          </div>
          {c.full_text_excerpt && (
            <>
              <button
                onClick={() => setOpen(!open)}
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary"
                aria-expanded={open}
              >
                {t.exactText}
                <ChevronDown className={`h-3.5 w-3.5 transition ${open ? "rotate-180" : ""}`} />
              </button>
              {open && (
                <blockquote className="mt-2 border-l-2 border-accent/60 bg-accent-soft/40 py-2 pl-3 pr-2 font-display text-[13px] italic leading-relaxed text-ink/90">
                  {c.full_text_excerpt}
                </blockquote>
              )}
            </>
          )}
        </div>
      </div>
    </li>
  );
}

export default function SourceList({ citations, related, highlight, idPrefix, answer, done }) {
  const t = useT();
  const [showAll, setShowAll] = useState(false);
  if (!citations.length) return null;

  // Lead with the sources the answer actually cites; keep the rest one click away.
  const citedRefs = new Set([...answer.matchAll(/\[(\d+)\]/g)].map((m) => Number(m[1])));
  const cited = citations.filter((c) => citedRefs.has(c.ref));
  const primary = done && cited.length ? cited : citations;
  const extra = citations.filter((c) => !primary.includes(c));
  const visible = showAll || highlight ? [...primary, ...extra] : primary;

  return (
    <div className="mt-4 space-y-3">
      <div className="eyebrow">{t.sources}</div>
      <ol className="grid gap-2 sm:grid-cols-2">
        {visible.map((c) => (
          <SourceCard key={c.id} c={c} id={`${idPrefix}-${c.ref}`} highlighted={highlight === c.ref} />
        ))}
      </ol>
      {extra.length > 0 && !(showAll || highlight) && (
        <button onClick={() => setShowAll(true)} className="text-xs font-medium text-muted transition hover:text-ink">
          + {extra.length} {t.moreSources}
        </button>
      )}
      {related.length > 0 && (
        <div className="pt-1">
          <div className="eyebrow mb-2 flex items-center gap-1.5">
            <GitBranch className="h-3 w-3" />
            {t.alsoRelevant}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {related.map((r) => (
              <a
                key={r.id}
                href={r.source_url}
                target="_blank"
                rel="noreferrer"
                title={`${r.instrument}, ${r.citation} · ${r.relation.toLowerCase().replace(/_/g, " ")}`}
                className="inline-flex max-w-full items-center gap-1.5 truncate rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted transition hover:border-primary/40 hover:text-primary"
              >
                <span className="truncate">{r.title}</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
