export default function PageHeader({ icon: Icon, title, children }) {
  return (
    <header className="mb-6 animate-fade-up">
      <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary">
        <Icon className="h-5 w-5" />
      </div>
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">{title}</h1>
      {children && <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">{children}</p>}
    </header>
  );
}
