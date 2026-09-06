import CitationCard from "./CitationCard.jsx";
import RelatedCitationCard from "./RelatedCitationCard.jsx";
import ConfidenceBadge from "./ConfidenceBadge.jsx";
import EscalateButton from "./EscalateButton.jsx";

export default function JurisdictionAnswerBlock({ answer }) {
  const isIndia = answer.jurisdiction === "India";
  const accent = isIndia ? "border-india" : "border-intl";
  const chipBg = isIndia ? "bg-india-light text-india" : "bg-intl-light text-intl";

  return (
    <div className={`border-l-4 ${accent} rounded-lg bg-white p-4 space-y-3`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <span className={`text-xs font-bold uppercase tracking-wide px-2 py-1 rounded ${chipBg}`}>
          {answer.label || answer.jurisdiction}
        </span>
        <ConfidenceBadge level={answer.confidence} />
      </div>

      <p className="text-sm whitespace-pre-line text-stone-800 leading-relaxed">{answer.answer_text}</p>

      {answer.abstained && (
        <div className="pt-1">
          <EscalateButton />
        </div>
      )}

      {answer.citations.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">
            Sources ({answer.citations.length})
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {answer.citations.map((c) => (
              <CitationCard key={c.id} citation={c} />
            ))}
          </div>
        </div>
      )}

      {answer.graph_related && answer.graph_related.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">
            Also related, via the knowledge graph ({answer.graph_related.length})
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {answer.graph_related.map((c) => (
              <RelatedCitationCard key={`${c.id}-${c.relation}`} citation={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
