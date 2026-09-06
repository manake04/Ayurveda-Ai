const LABELS = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" };

export default function ConfidenceBadge({ level }) {
  return (
    <span className={`text-xs font-semibold px-2 py-1 rounded-full border confidence-${level}`}>
      {LABELS[level] || level}
    </span>
  );
}
