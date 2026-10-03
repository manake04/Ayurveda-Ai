import { ExternalLink, Lock, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api.js";
import ErrorNote from "../ui/ErrorNote.jsx";
import PageHeader from "../ui/PageHeader.jsx";

export default function SourcesView() {
  const [sources, setSources] = useState([]);
  const [connectors, setConnectors] = useState([]);
  const [error, setError] = useState(null);

  const loadConnectors = useCallback(() => api.connectors().then(setConnectors), []);

  useEffect(() => {
    Promise.all([api.sources(), loadConnectors()])
      .then(([s]) => setSources(s.free))
      .catch((e) => setError(e.message));
  }, [loadConnectors]);

  return (
    <>
      <PageHeader icon={ShieldCheck} title="Sources & privacy">
        Go straight to the official databases behind the answers, decide whether paid databases may ever be used for
        you, and see or delete what this app has recorded about your browser.
      </PageHeader>
      {error && <ErrorNote>{error}</ErrorNote>}

      <section className="mb-10">
        <h2 className="eyebrow mb-3">Free official sources</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {sources.map((s) => (
            <a
              key={s.url}
              href={s.url}
              target="_blank"
              rel="noreferrer"
              className="card group p-4 transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lift"
            >
              <div className="flex items-center justify-between gap-2 text-sm font-medium text-ink group-hover:text-primary">
                {s.name}
                <ExternalLink className="h-4 w-4 opacity-40 group-hover:opacity-100" />
              </div>
              <p className="mt-1 text-xs leading-relaxed text-muted">{s.description}</p>
            </a>
          ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="eyebrow mb-1">Your paid subscriptions</h2>
        <p className="mb-3 text-sm text-muted">
          No paid database is connected yet. If one is added, it will only be searched for you if you allow it here.
          Every change is logged and can be reversed.
        </p>
        <div className="card divide-y divide-line">
          {connectors.map((c) => (
            <ConnectorRow
              key={c.id}
              connector={c}
              onChange={(granted) =>
                setConnectors((all) => all.map((x) => (x.id === c.id ? { ...x, consent: granted } : x)))
              }
            />
          ))}
        </div>
      </section>

      <YourData onErased={loadConnectors} />
    </>
  );
}

function ConnectorRow({ connector, onChange }) {
  const [saving, setSaving] = useState(false);
  const toggle = async (granted) => {
    setSaving(true);
    try {
      await api.setConsent(connector.id, granted);
      onChange(granted);
    } finally {
      setSaving(false);
    }
  };
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 px-5 py-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-medium text-ink">
          {connector.name}
          <span className="inline-flex items-center gap-1 rounded-full bg-sunken px-2 py-0.5 text-[10px] font-medium text-faint">
            <Lock className="h-2.5 w-2.5" /> Not connected
          </span>
        </div>
        <p className="mt-0.5 text-xs text-muted">{connector.description}</p>
      </div>
      <input
        type="checkbox"
        className="peer sr-only"
        checked={connector.consent}
        disabled={saving}
        onChange={(e) => toggle(e.target.checked)}
      />
      <span
        aria-hidden="true"
        className="relative h-5 w-9 shrink-0 rounded-full bg-line transition after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-surface after:shadow after:transition peer-checked:bg-primary peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-primary/50"
      />
    </label>
  );
}

// Stored in UTC; shown in the viewer's local time.
const formatTime = (ts) => new Date(ts).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

const DESCRIBE = {
  question: (d) =>
    `Asked a question (${d.query_chars} characters, ${d.jurisdiction}${d.mode === "agentic" ? ", deep research" : ""}). ` +
    (d.query ? `"${d.query}"` : "The text itself was not stored."),
  consent: (d) => `${d.granted ? "Allowed" : "Withdrew permission for"} ${d.connector}.`,
  escalation: (d) => `Sent question ${d.id} to a facilitator${d.contact ? ` with contact ${d.contact}` : ""}.`,
};

function YourData({ onErased }) {
  const [items, setItems] = useState(null);
  const [message, setMessage] = useState(null);

  const load = useCallback(() => {
    api
      .activity()
      .then((r) => setItems(r.items))
      .catch((e) => setMessage(e.message));
  }, []);
  useEffect(load, [load]);

  const erase = async () => {
    const r = await api.eraseActivity();
    setMessage(`Deleted ${r.deleted} record${r.deleted === 1 ? "" : "s"}.`);
    load();
    onErased?.(); // withdrawn consents must show as off again
  };

  return (
    <section>
      <div className="mb-1 flex items-center justify-between">
        <h2 className="eyebrow">Your data</h2>
        <button onClick={load} className="btn-ghost px-2 py-1 text-xs">
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>
      <p className="mb-3 text-sm text-muted">
        Records linked to this browser's anonymous id. Questions are stored as a fingerprint and length, not their text.
        Records are deleted automatically after the retention period.
      </p>
      <div className="card p-2">
        {items?.length === 0 && <p className="px-3 py-4 text-sm text-faint">Nothing recorded for this browser.</p>}
        <ul className="max-h-80 divide-y divide-line overflow-y-auto">
          {items?.map((item, i) => (
            <li key={i} className="flex gap-3 px-3 py-2.5 text-sm">
              <time className="w-36 shrink-0 font-mono text-[11px] text-faint">{formatTime(item.ts)}</time>
              <span className="text-ink/90">{(DESCRIBE[item.type] || (() => item.type))(item.detail)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button onClick={erase} disabled={!items?.length} className="btn-outline text-danger hover:border-danger/50">
          <Trash2 className="h-4 w-4" /> Delete my data
        </button>
        {message && <span className="text-sm text-muted">{message}</span>}
      </div>
    </section>
  );
}
