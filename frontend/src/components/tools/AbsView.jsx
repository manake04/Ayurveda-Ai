import { CheckCircle2, CircleDashed, Leaf } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../lib/api.js";
import ErrorNote from "../ui/ErrorNote.jsx";
import PageHeader from "../ui/PageHeader.jsx";

const FACTS = [
  ["uses_biological_material", "The product uses biological material (plant, microbial or animal-derived)"],
  ["sourced_from_india", "That material is sourced from India"],
  ["ip_or_commercialisation_sought", "You plan to seek IP rights or sell the product"],
  ["user_is_registered_ayush_practitioner", "You are a registered AYUSH practitioner"],
  ["knowledge_is_codified_traditional_knowledge", "It is based on codified traditional knowledge (a recognised classical text)"],
  ["exporting_or_partnering_abroad", "You plan to export or partner with an organisation abroad"],
];

export default function AbsView() {
  const [facts, setFacts] = useState(() => Object.fromEntries(FACTS.map(([k]) => [k, false])));
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .absChecklist(facts)
      .then((r) => !cancelled && (setResult(r), setError(null)))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [facts]);

  const applying = result?.checklist.filter((i) => i.applies).length ?? 0;

  return (
    <>
      <PageHeader icon={Leaf} title="Access & benefit-sharing checklist">
        Using Indian biological resources can trigger approval and benefit-sharing duties under the Biological Diversity
        Act and international treaties. Tick what applies; the checklist updates as you go.
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <fieldset className="card h-fit p-2">
          <legend className="sr-only">Your situation</legend>
          {FACTS.map(([key, label]) => (
            <label
              key={key}
              className="flex cursor-pointer items-start justify-between gap-4 rounded-xl px-4 py-3 text-sm leading-snug text-ink transition hover:bg-sunken"
            >
              {label}
              <input
                type="checkbox"
                className="peer sr-only"
                checked={facts[key]}
                onChange={(e) => setFacts({ ...facts, [key]: e.target.checked })}
              />
              <span
                aria-hidden="true"
                className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full bg-line transition after:absolute after:left-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-surface after:shadow after:transition peer-checked:bg-primary peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-primary/50"
              />
            </label>
          ))}
        </fieldset>

        <div className="space-y-3">
          {error && <ErrorNote>{error}</ErrorNote>}
          {result && (
            <>
              <div className="eyebrow">
                {applying} of {result.checklist.length} duties likely apply
              </div>
              {result.checklist.map((item) => (
                <div
                  key={item.step}
                  className={`rounded-2xl border p-4 transition ${
                    item.applies ? "border-accent/40 bg-accent-soft/50" : "border-line bg-surface"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {item.applies ? (
                      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                    ) : (
                      <CircleDashed className="mt-0.5 h-5 w-5 shrink-0 text-faint" />
                    )}
                    <div className="min-w-0">
                      <div className={`text-sm font-medium ${item.applies ? "text-ink" : "text-muted"}`}>{item.step}</div>
                      <p className={`mt-1 text-sm leading-relaxed ${item.applies ? "text-ink/80" : "text-faint"}`}>{item.detail}</p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {item.citation_ids.map((id) => (
                          <span key={id} className="rounded-md bg-surface/70 px-1.5 py-0.5 font-mono text-[10.5px] text-faint">
                            {id}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </>
  );
}
