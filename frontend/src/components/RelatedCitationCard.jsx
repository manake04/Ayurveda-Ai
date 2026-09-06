const RELATION_LABELS = {
  SUPPORTS: "supports",
  ENFORCES: "enforced by",
  ENFORCED_BY: "enforced by",
  APPLIES_ALONGSIDE: "applies alongside",
  DETAILS: "detailed in",
  IMPLEMENTS: "implements",
  REINFORCED_BY: "reinforced by",
  RELATED_TO: "related to",
  COMPLEMENTS: "complements",
  CONSTRAINED_BY: "constrained by",
  LABELLING_GOVERNED_BY: "labelling governed by",
  ALTERNATIVE_TO: "alternative to",
  INTERNATIONAL_COUNTERPART: "international counterpart",
  INTERNATIONAL_ROUTE: "international route via",
  GOVERNED_BY_BASELINE: "baseline governed by",
  PRIORITY_GOVERNED_BY: "priority governed by",
  ALTERNATIVE_STRATEGY: "alternative strategy",
  ANALOGOUS_TO: "analogous to",
  UMBRELLA_OVER: "umbrella over",
};

/** A citation surfaced via 1-hop knowledge-graph expansion rather than direct lexical
 * retrieval -- lexically dissimilar from the query, but connected to a directly-cited
 * document through the graph. Rendered distinctly so it reads as "also worth knowing
 * about" rather than a primary source for the answer text itself. */
export default function RelatedCitationCard({ citation }) {
  const relationLabel = RELATION_LABELS[citation.relation] || citation.relation?.toLowerCase().replace(/_/g, " ");

  return (
    <a
      href={citation.source_url}
      target="_blank"
      rel="noreferrer"
      className="block border border-dashed border-amber-300 rounded-lg p-3 hover:border-amber-500 hover:shadow-sm transition-all bg-amber-50/40"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-stone-900">{citation.title}</div>
          <div className="text-xs text-stone-500 mt-0.5">
            {citation.instrument} &middot; {citation.citation}
          </div>
        </div>
        <span className="shrink-0 text-[10px] uppercase tracking-wide font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
          {citation.jurisdiction}
        </span>
      </div>
      <div className="text-xs text-amber-700 mt-2 font-medium">
        {relationLabel}
        {citation.hops > 1 ? ` (${citation.hops} hops)` : ""} via the knowledge graph
      </div>
    </a>
  );
}
