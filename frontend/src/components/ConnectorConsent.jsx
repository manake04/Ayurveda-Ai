import { useState } from "react";
import { api } from "../api.js";

export default function ConnectorConsent() {
  const [name, setName] = useState("My paid legal-research subscription");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  async function grant(granted) {
    setLoading(true);
    try {
      const res = await api.connectorConsent(name, granted);
      setStatus(res);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-5 max-w-2xl space-y-3">
      <div className="text-xs font-semibold text-stone-400 uppercase tracking-wide">
        Paid-source connector permission (demo)
      </div>
      <p className="text-sm text-stone-600">
        This assistant only uses your own paid subscriptions (e.g. a paid case-law database) with your
        explicit, logged permission. No real connector is wired up in this MVP -- this demonstrates the
        consent-and-audit pattern the architecture is built around.
      </p>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm"
      />
      <div className="flex gap-2">
        <button
          disabled={loading}
          onClick={() => grant(true)}
          className="bg-india text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
        >
          Grant permission
        </button>
        <button
          disabled={loading}
          onClick={() => grant(false)}
          className="bg-stone-200 text-stone-800 text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-50"
        >
          Revoke
        </button>
      </div>
      {status && (
        <div className="text-sm bg-stone-50 border border-stone-200 rounded-lg p-3">
          <div className="font-medium">{status.granted ? "Granted" : "Revoked"} at {status.logged_at}</div>
          <div className="text-stone-600 mt-1">{status.message}</div>
        </div>
      )}
    </div>
  );
}
