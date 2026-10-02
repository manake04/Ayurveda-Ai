export default function Logo({ className = "h-8 w-8" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="9" className="fill-primary" />
      <path d="M9 22.5c0-8 6-13.5 14-13.5 0 8-5 14-13 14" fill="none" className="stroke-accent-soft" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M9.5 22.5l8-8" className="stroke-accent-soft" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}
