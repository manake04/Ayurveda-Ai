const OPTIONS = [
  { value: "india", label: "India" },
  { value: "international", label: "International" },
  { value: "both", label: "Both (kept separate)" },
];

export default function JurisdictionToggle({ value, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-stone-300 bg-white overflow-hidden">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1.5 text-sm font-medium transition-colors ${
            value === opt.value
              ? "bg-stone-900 text-white"
              : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
