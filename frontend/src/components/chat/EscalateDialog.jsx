import { CheckCircle2, ExternalLink, Mail, UserRound, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api.js";
import { useConfig } from "../../lib/config.js";
import { useT } from "../../lib/i18n.js";
import ErrorNote from "../ui/ErrorNote.jsx";

/** Hand a question to a human IP facilitator, with explicit consent. */
export default function EscalateDialog({ question, jurisdiction, onClose }) {
  const t = useT();
  const { escalation } = useConfig();
  const ref = useRef(null);
  const [text, setText] = useState(question);
  const [contact, setContact] = useState("");
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState({ status: "idle" });

  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setState({ status: "sending" });
    try {
      const ticket = await api.escalate({ question: text, jurisdiction, contact: contact || null, consent });
      setState({ status: "sent", ticket });
    } catch (err) {
      setState({ status: "error", message: err.message });
    }
  };

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="w-[min(32rem,calc(100vw-2rem))] rounded-2xl border border-line bg-surface p-0 text-ink shadow-lift backdrop:bg-ink/40 backdrop:backdrop-blur-sm"
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-intl-soft text-intl">
            <UserRound className="h-4 w-4" />
          </span>
          <h2 className="font-display text-lg font-semibold">{t.escalateTitle}</h2>
        </div>
        <button onClick={onClose} className="btn-ghost -mr-2 p-2" aria-label={t.close}>
          <X className="h-4 w-4" />
        </button>
      </div>

      {state.status === "sent" ? (
        <div className="space-y-4 px-6 py-6">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <p className="text-[15px] leading-relaxed">
              {t.escalateDone} <span className="font-mono font-semibold">{state.ticket.id}</span>.
            </p>
          </div>
          <Contacts escalation={escalation} t={t} />
          <div className="flex justify-end">
            <button className="btn-primary" onClick={onClose}>
              {t.close}
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4 px-6 py-5">
          <p className="text-sm leading-relaxed text-muted">{t.escalateBody}</p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            required
            minLength={3}
            className="w-full resize-y rounded-xl border border-line bg-bg px-3 py-2 text-sm focus:border-primary/50 focus:outline-none"
          />
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted">{t.escalateContact}</span>
            <input
              value={contact}
              onChange={(e) => setContact(e.target.value)}
              maxLength={200}
              className="w-full rounded-xl border border-line bg-bg px-3 py-2 text-sm focus:border-primary/50 focus:outline-none"
            />
          </label>
          <label className="flex cursor-pointer items-start gap-2.5 text-sm">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5 h-4 w-4 accent-[rgb(var(--primary))]"
            />
            {t.escalateConsent}
          </label>
          {state.status === "error" && <ErrorNote>{state.message}</ErrorNote>}
          <Contacts escalation={escalation} t={t} />
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-ghost" onClick={onClose}>
              {t.cancel}
            </button>
            <button className="btn-primary" disabled={!consent || text.trim().length < 3 || state.status === "sending"}>
              {t.escalateSubmit}
            </button>
          </div>
        </form>
      )}
    </dialog>
  );
}

function Contacts({ escalation, t }) {
  if (!escalation) return null;
  return (
    <div className="rounded-xl bg-sunken/70 px-4 py-3 text-xs text-muted">
      <div className="mb-1.5 font-medium text-ink">
        {t.escalateAlso}
        {escalation.name ? ` ${escalation.name}` : ""}:
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {escalation.email && (
          <a href={`mailto:${escalation.email}`} className="inline-flex items-center gap-1 text-primary hover:underline">
            <Mail className="h-3.5 w-3.5" /> {escalation.email}
          </a>
        )}
        {escalation.url && (
          <a href={escalation.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
            {escalation.url_label} <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </div>
  );
}
