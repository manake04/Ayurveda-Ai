import { useEffect, useMemo, useState } from "react";
import AskView from "./components/chat/AskView.jsx";
import GraphView from "./components/graph/GraphView.jsx";
import Page from "./components/layout/Page.jsx";
import Sidebar from "./components/layout/Sidebar.jsx";
import AbsView from "./components/tools/AbsView.jsx";
import ClassifyView from "./components/tools/ClassifyView.jsx";
import PriorArtView from "./components/tools/PriorArtView.jsx";
import { useChat } from "./hooks/useChat.js";
import { api } from "./lib/api.js";
import { LangContext, STRINGS } from "./lib/i18n.js";

const stored = (key, fallback) => {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
};
const store = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
};

export default function App() {
  const [view, setView] = useState("ask");
  const [lang, setLang] = useState(() => stored("lang", "en"));
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "light");
  const [menuOpen, setMenuOpen] = useState(false);
  const [health, setHealth] = useState(null);
  const chat = useChat();

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ error: true }));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    store("theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
    store("lang", lang);
  }, [lang]);

  const langValue = useMemo(() => ({ lang, t: STRINGS[lang] }), [lang]);
  const go = (v) => {
    setView(v);
    setMenuOpen(false);
  };
  const openMenu = () => setMenuOpen(true);

  return (
    <LangContext.Provider value={langValue}>
      <div className="flex h-dvh overflow-hidden">
        <Sidebar
          view={view}
          onView={go}
          onNewChat={() => {
            chat.reset();
            go("ask");
          }}
          lang={lang}
          onLang={setLang}
          theme={theme}
          onTheme={setTheme}
          health={health}
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
        />
        <main className="min-w-0 flex-1">
          {view === "ask" && <AskView chat={chat} lang={lang} onMenu={openMenu} />}
          {view === "classify" && (
            <Page onMenu={openMenu}>
              <ClassifyView />
            </Page>
          )}
          {view === "abs" && (
            <Page onMenu={openMenu} wide>
              <AbsView />
            </Page>
          )}
          {view === "prior-art" && (
            <Page onMenu={openMenu}>
              <PriorArtView />
            </Page>
          )}
          {view === "graph" && (
            <Page onMenu={openMenu} wide>
              <GraphView />
            </Page>
          )}
        </main>
      </div>
    </LangContext.Provider>
  );
}
