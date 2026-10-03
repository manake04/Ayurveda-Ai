import { ArrowUp, Languages, Sparkles, Square } from "lucide-react";
import { useEffect, useRef } from "react";
import { useConfig } from "../../lib/config.js";
import { useT } from "../../lib/i18n.js";
import Segmented from "../ui/Segmented.jsx";

export default function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  busy,
  jurisdiction,
  onJurisdiction,
  deep,
  onDeep,
  language,
  onLanguage,
  autoFocus,
}) {
  const t = useT();
  const config = useConfig();
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  const refocus = () => ref.current?.focus(); // keep Enter-to-send working after using a control
  const canSend = value.trim().length >= 3 && !busy;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSend) onSubmit();
      }}
      className="card overflow-hidden p-2 transition focus-within:border-primary/40 focus-within:shadow-lift"
    >
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (canSend) onSubmit();
          }
        }}
        placeholder={t.placeholder}
        aria-label={t.placeholder}
        className="block w-full resize-none bg-transparent px-3 py-2.5 text-[15px] leading-6 text-ink placeholder:text-faint focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
      />
      <div className="flex flex-wrap items-center gap-2 px-1 pt-1">
        <Segmented
          size="sm"
          label={t.scope}
          value={jurisdiction}
          onChange={(v) => {
            onJurisdiction(v);
            refocus();
          }}
          options={[
            { value: "india", label: t.india },
            { value: "international", label: t.international },
            { value: "both", label: t.both },
          ]}
        />
        {config.agentic && (
          <button
            type="button"
            aria-pressed={deep}
            title={t.deepResearchHint}
            onClick={() => {
              onDeep(!deep);
              refocus();
            }}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
              deep ? "bg-accent-soft text-accent ring-1 ring-accent/40" : "text-muted hover:bg-sunken hover:text-ink"
            }`}
          >
            <Sparkles className="h-3.5 w-3.5" />
            {t.deepResearch}
          </button>
        )}
        <label className="inline-flex items-center gap-1 rounded-lg px-1.5 py-1 text-xs text-muted transition focus-within:text-ink hover:bg-sunken">
          <Languages className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="sr-only">{t.answerLanguage}</span>
          <select
            value={language}
            onChange={(e) => {
              onLanguage(e.target.value);
              refocus();
            }}
            title={t.answerLanguage}
            className="cursor-pointer bg-transparent py-0.5 pr-1 font-medium focus:outline-none"
          >
            {config.languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
        <div className="ml-auto">
          {busy ? (
            <button type="button" onClick={onStop} className="btn-outline h-9 w-9 rounded-xl p-0" aria-label={t.stop}>
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button type="submit" disabled={!canSend} className="btn-primary h-9 w-9 rounded-xl p-0" aria-label={t.send}>
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
