import { useEffect, useState } from "react";
import { api } from "./api.js";
import DisclaimerBanner from "./components/DisclaimerBanner.jsx";
import JurisdictionToggle from "./components/JurisdictionToggle.jsx";
import LanguageToggle from "./components/LanguageToggle.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import ClassifierWizard from "./components/ClassifierWizard.jsx";
import ABSHelper from "./components/ABSHelper.jsx";
import TKDLPointer from "./components/TKDLPointer.jsx";
import ConnectorConsent from "./components/ConnectorConsent.jsx";
import GraphExplorer from "./components/GraphExplorer.jsx";

const TABS = [
  { id: "chat", label: "Ask a question" },
  { id: "graph", label: "Knowledge graph" },
  { id: "classify", label: "Classify my formulation" },
  { id: "abs", label: "ABS helper" },
  { id: "tkdl", label: "TKDL / prior-art pointer" },
  { id: "connectors", label: "Paid-source permissions" },
];

const UI_STRINGS_FALLBACK = {
  app_title: "IP-SAKTI Sahayak",
  tagline: "Multilingual, source-cited IP & regulatory guidance for Ayurveda",
  ask_placeholder: "Ask an IP or regulatory question about your Ayurvedic product…",
  disclaimer: "",
};

export default function App() {
  const [jurisdiction, setJurisdiction] = useState("india");
  const [language, setLanguage] = useState("en");
  const [tab, setTab] = useState("chat");
  const [uiStrings, setUiStrings] = useState(UI_STRINGS_FALLBACK);
  const [health, setHealth] = useState(null);
  const [backendError, setBackendError] = useState(false);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setBackendError(true));
  }, []);

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"}/i18n/${language}`)
      .then((r) => r.json())
      .then(setUiStrings)
      .catch(() => setUiStrings(UI_STRINGS_FALLBACK));
  }, [language]);

  return (
    <div className="min-h-screen flex flex-col">
      <DisclaimerBanner text={uiStrings.disclaimer} />

      <header className="border-b border-stone-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-stone-900">{uiStrings.app_title}</h1>
            <p className="text-sm text-stone-500">{uiStrings.tagline}</p>
          </div>
          <div className="flex items-center gap-2">
            <LanguageToggle value={language} onChange={setLanguage} />
            <JurisdictionToggle value={jurisdiction} onChange={setJurisdiction} />
          </div>
        </div>
        <div className="max-w-5xl mx-auto px-4 flex gap-1 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`text-sm font-medium px-3 py-2 border-b-2 whitespace-nowrap transition-colors ${
                tab === t.id
                  ? "border-stone-900 text-stone-900"
                  : "border-transparent text-stone-500 hover:text-stone-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      {backendError && (
        <div className="max-w-5xl mx-auto w-full px-4 pt-4">
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            Can't reach the backend API. Start it with <code className="font-mono">uvicorn app.main:app --reload</code>{" "}
            from the <code className="font-mono">backend/</code> folder (see the README), then reload this page.
          </div>
        </div>
      )}

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">
        {tab === "chat" && <ChatWindow jurisdiction={jurisdiction} language={language} uiStrings={uiStrings} />}
        {tab === "graph" && <GraphExplorer />}
        {tab === "classify" && <ClassifierWizard />}
        {tab === "abs" && <ABSHelper />}
        {tab === "tkdl" && <TKDLPointer />}
        {tab === "connectors" && <ConnectorConsent />}
      </main>

      <footer className="text-xs text-stone-400 text-center py-4 border-t border-stone-200">
        IP-SAKTI Sahayak MVP &middot; {health ? `${health.corpus_documents} curated corpus documents indexed` : "…"}{" "}
        &middot; Built for Smart India Hackathon, Problem Statement 26045
      </footer>
    </div>
  );
}
