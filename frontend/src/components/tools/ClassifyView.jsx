import { ArrowLeft, FlaskConical, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../lib/api.js";
import ErrorNote from "../ui/ErrorNote.jsx";
import PageHeader from "../ui/PageHeader.jsx";

const MAX_QUESTIONS = 5; // longest path through the classifier tree

export default function ClassifyView() {
  const [answers, setAnswers] = useState([]);
  const [step, setStep] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .classify(answers)
      .then((s) => !cancelled && setStep(s))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [answers]);

  return (
    <>
      <PageHeader icon={FlaskConical} title="Classify your formulation">
        IP and licensing rules depend on how your product is classified. Answer a few yes/no questions to find its
        category, what it needs to be licensed, and how it can be protected.
      </PageHeader>

      {error && <ErrorNote>{error}</ErrorNote>}

      {step && !step.done && (
        <div className="card animate-fade-up p-6 sm:p-8" key={step.question_id}>
          <div className="mb-5 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${((answers.length + 1) / MAX_QUESTIONS) * 100}%` }}
              />
            </div>
            <span className="eyebrow">Question {answers.length + 1}</span>
          </div>
          <p className="font-display text-xl leading-snug text-ink sm:text-[22px]">{step.question_text}</p>
          <div className="mt-6 flex flex-wrap gap-2">
            <button className="btn-primary min-w-24" onClick={() => setAnswers([...answers, "yes"])}>
              Yes
            </button>
            <button className="btn-outline min-w-24" onClick={() => setAnswers([...answers, "no"])}>
              No
            </button>
            {answers.length > 0 && (
              <button className="btn-ghost ml-auto" onClick={() => setAnswers(answers.slice(0, -1))}>
                <ArrowLeft className="h-4 w-4" /> Back
              </button>
            )}
          </div>
        </div>
      )}

      {step?.done && step.result && (
        <div className="card animate-fade-up overflow-hidden">
          <div className="border-b border-line bg-primary-soft/60 px-6 py-5 sm:px-8">
            <div className="eyebrow mb-1">Category</div>
            <h2 className="font-display text-2xl font-semibold text-primary">{step.result.category}</h2>
          </div>
          <dl className="space-y-5 px-6 py-6 sm:px-8">
            <div>
              <dt className="eyebrow mb-1.5">What it needs</dt>
              <dd className="text-[15px] leading-relaxed text-ink">{step.result.requires}</dd>
            </div>
            <div>
              <dt className="eyebrow mb-1.5">IP &amp; benefit-sharing position</dt>
              <dd className="text-[15px] leading-relaxed text-ink">{step.result.ip_abs_posture}</dd>
            </div>
            <div>
              <dt className="eyebrow mb-2">Sources</dt>
              <dd className="flex flex-wrap gap-1.5">
                {step.result.relevant_corpus_ids.map((id) => (
                  <span key={id} className="rounded-md bg-sunken px-2 py-1 font-mono text-[11px] text-muted">
                    {id}
                  </span>
                ))}
              </dd>
            </div>
          </dl>
          <div className="border-t border-line px-6 py-4 sm:px-8">
            <button className="btn-ghost -ml-3" onClick={() => setAnswers([])}>
              <RotateCcw className="h-4 w-4" /> Start over
            </button>
          </div>
        </div>
      )}

      {!step && !error && <div className="skeleton h-48 rounded-2xl" />}
    </>
  );
}
