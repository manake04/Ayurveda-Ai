import {
  FlaskConical,
  Leaf,
  MessageSquareText,
  Moon,
  Network,
  SearchCheck,
  ShieldCheck,
  SquarePen,
  Sun,
  X,
} from "lucide-react";
import { useT } from "../../lib/i18n.js";
import Logo from "../ui/Logo.jsx";
import Segmented from "../ui/Segmented.jsx";

export const VIEWS = [
  { id: "ask", icon: MessageSquareText, key: "navAsk" },
  { id: "classify", icon: FlaskConical, key: "navClassify" },
  { id: "abs", icon: Leaf, key: "navAbs" },
  { id: "prior-art", icon: SearchCheck, key: "navPriorArt" },
  { id: "graph", icon: Network, key: "navGraph" },
  { id: "sources", icon: ShieldCheck, key: "navSources" },
];

export default function Sidebar({ view, onView, onNewChat, lang, onLang, theme, onTheme, health, open, onClose }) {
  const t = useT();
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-ink/30 backdrop-blur-sm lg:hidden" onClick={onClose} />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-line bg-surface/95 backdrop-blur transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center gap-3 px-5 pb-4 pt-5">
          <Logo className="h-9 w-9" />
          <div className="min-w-0 flex-1">
            <div className="truncate font-display text-[17px] font-semibold leading-tight">{t.appName}</div>
            <div className="truncate text-xs text-muted">{t.tagline}</div>
          </div>
          <button className="btn-ghost -mr-2 p-2 lg:hidden" onClick={onClose} aria-label="Close menu">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-3">
          <button onClick={onNewChat} className="btn-outline w-full justify-start">
            <SquarePen className="h-4 w-4" />
            {t.newChat}
          </button>
        </div>

        <nav className="mt-4 flex-1 space-y-0.5 px-3" aria-label="Main">
          {VIEWS.map(({ id, icon: Icon, key }) => {
            const active = view === id;
            return (
              <button
                key={id}
                onClick={() => onView(id)}
                aria-current={active ? "page" : undefined}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  active ? "bg-primary-soft text-primary" : "text-muted hover:bg-sunken hover:text-ink"
                }`}
              >
                <Icon className="h-[18px] w-[18px]" />
                {t[key]}
              </button>
            );
          })}
        </nav>

        <div className="space-y-3 border-t border-line px-4 py-4">
          <div className="flex items-center justify-between gap-2">
            <Segmented
              size="sm"
              label="Language"
              value={lang}
              onChange={onLang}
              options={[
                { value: "en", label: "EN" },
                { value: "hi", label: "हिंदी" },
              ]}
            />
            <button
              onClick={() => onTheme(theme === "dark" ? "light" : "dark")}
              className="btn-ghost p-2"
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          </div>
          <StatusLine health={health} />
        </div>
      </aside>
    </>
  );
}

function StatusLine({ health }) {
  const ok = health && !health.error;
  return (
    <div className="flex items-center gap-2 text-[11px] text-faint" title={ok ? `Models: ${health.llms.join(" → ")} · embeddings: ${health.embeddings}` : undefined}>
      <span className={`h-1.5 w-1.5 rounded-full ${health ? (ok ? "bg-primary" : "bg-danger") : "bg-faint animate-pulse"}`} />
      {!health && "Connecting…"}
      {ok && `${health.documents} sources · ${health.llms[0].replace(/^\w+:/, "")}`}
      {health?.error && "Server offline"}
    </div>
  );
}
