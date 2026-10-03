import { ExternalLink, Search, SearchCheck } from "lucide-react";
import { useState } from "react";
import { api } from "../../lib/api.js";
import ErrorNote from "../ui/ErrorNote.jsx";
import PageHeader from "../ui/PageHeader.jsx";

export default function PriorArtView() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async (e) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await api.tkdlPointer(query.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader icon={SearchCheck} title="Prior-art search">
        Check whether your formulation is already known before you file. The Traditional Knowledge Digital Library
        (TKDL) is only open to patent examiners, so this points you to the public databases you can search yourself.
      </PageHeader>

      <form onSubmit={run} className="card flex items-center gap-2 p-2">
        <Search className="ml-3 h-4 w-4 shrink-0 text-faint" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. ashwagandha churna for stress"
          aria-label="Formulation or ingredient"
          className="min-w-0 flex-1 bg-transparent px-1 py-2 text-[15px] placeholder:text-faint focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0"
        />
        <button className="btn-primary" disabled={loading || query.trim().length < 2}>
          {loading ? "Searching…" : "Get guidance"}
        </button>
      </form>

      {error && (
        <div className="mt-4">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      {result && (
        <div className="mt-6 animate-fade-up space-y-6">
          <p className="text-[15px] leading-relaxed text-ink">{result.guidance}</p>
          <div>
            <div className="eyebrow mb-3">Search these databases</div>
            <div className="grid gap-3 sm:grid-cols-2">
              {result.search_links.map((l) => (
                <a
                  key={l.url}
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  className="card group p-4 transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lift"
                >
                  <div className="flex items-center justify-between gap-2 text-sm font-medium text-ink group-hover:text-primary">
                    {l.name}
                    <ExternalLink className="h-4 w-4 opacity-40 group-hover:opacity-100" />
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{l.note}</p>
                </a>
              ))}
            </div>
          </div>
          <a href={result.tkdl_source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
            About TKDL <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      )}
    </>
  );
}
