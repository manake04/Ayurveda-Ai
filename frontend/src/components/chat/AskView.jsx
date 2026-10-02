import { ArrowUpRight, Menu } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useT } from "../../lib/i18n.js";
import Composer from "./Composer.jsx";
import Turn from "./Turn.jsx";

export default function AskView({ chat, lang, onMenu }) {
  const t = useT();
  const [draft, setDraft] = useState("");
  const [jurisdiction, setJurisdiction] = useState("india");
  const bottomRef = useRef(null);
  const { turns, busy, send, stop } = chat;
  const empty = turns.length === 0;

  const language = lang === "hi" ? "hi" : "auto";
  const ask = (query, scope = jurisdiction) => {
    send({ query: query.trim(), jurisdiction: scope, language });
    setDraft("");
  };

  const lastTurn = turns[turns.length - 1];
  const lastAnswerLength = lastTurn ? Object.values(lastTurn.blocks).reduce((n, b) => n + b.answer.length, 0) : 0;
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, lastAnswerLength]);

  const composer = (
    <Composer
      value={draft}
      onChange={setDraft}
      onSubmit={() => ask(draft)}
      onStop={stop}
      busy={busy}
      jurisdiction={jurisdiction}
      onJurisdiction={setJurisdiction}
      autoFocus
    />
  );

  return (
    <div className="flex h-full flex-col">
      <MobileBar onMenu={onMenu} />
      {empty ? (
        <div className="flex flex-1 flex-col items-center justify-center px-4 pb-10">
          <div className="w-full max-w-2xl">
            <div className="mb-8 text-center animate-fade-up">
              <h1 className="font-display text-4xl font-semibold tracking-tight text-ink sm:text-[44px] sm:leading-[1.1]">
                {t.heroTitle}
              </h1>
              <p className="mx-auto mt-3 max-w-xl text-[15px] leading-relaxed text-muted">{t.heroSubtitle}</p>
            </div>
            {composer}
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {t.suggestions.map((s, i) => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  style={{ animationDelay: `${80 + i * 50}ms` }}
                  className="group flex animate-fade-up items-start justify-between gap-3 rounded-xl border border-line bg-surface/60 px-4 py-3 text-left text-sm leading-snug text-muted transition hover:border-primary/30 hover:bg-surface hover:text-ink"
                >
                  {s}
                  <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 opacity-0 transition group-hover:opacity-60" />
                </button>
              ))}
            </div>
            <p className="mt-6 text-center text-xs text-faint">{t.disclaimer}</p>
          </div>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-3xl space-y-12 px-4 py-8 sm:px-6">
              {turns.map((turn) => (
                <Turn key={turn.id} turn={turn} onRetry={(tr) => ask(tr.query, tr.jurisdiction)} />
              ))}
              <div ref={bottomRef} />
            </div>
          </div>
          <div className="bg-gradient-to-t from-bg via-bg to-bg/0 px-4 pb-4 pt-2 sm:px-6">
            <div className="mx-auto max-w-3xl">
              {composer}
              <p className="mt-2 text-center text-[11px] text-faint">{t.disclaimer}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export function MobileBar({ onMenu }) {
  const t = useT();
  return (
    <div className="flex items-center gap-2 border-b border-line px-3 py-2 lg:hidden">
      <button onClick={onMenu} className="btn-ghost p-2" aria-label="Open menu">
        <Menu className="h-5 w-5" />
      </button>
      <span className="font-display font-semibold">{t.appName}</span>
    </div>
  );
}
