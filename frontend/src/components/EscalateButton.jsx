export default function EscalateButton({ label = "Escalate to a human IP facilitator" }) {
  return (
    <a
      href="mailto:ip-facilitator@example-ayush-cell.gov.in?subject=IP-SAKTI%20Sahayak%20escalation"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-intl border border-intl/40 rounded-lg px-3 py-1.5 hover:bg-intl-light transition-colors"
    >
      <span aria-hidden>🧑‍⚖️</span> {label}
    </a>
  );
}
