import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function ClassifierWizard() {
  const [answers, setAnswers] = useState([]);
  const [step, setStep] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function loadStep(nextAnswers) {
    setLoading(true);
    setError(null);
    try {
      const res = await api.classifyStep(nextAnswers);
      setStep(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStep([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function answer(value) {
    const next = [...answers, value];
    setAnswers(next);
    loadStep(next);
  }

  function restart() {
    setAnswers([]);
    loadStep([]);
  }

  if (error) {
    return (
      <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
        Couldn't reach the backend: {error}.
      </div>
    );
  }
  if (loading || !step) {
    return <div className="text-sm text-stone-500 animate-pulse">Loading…</div>;
  }

  return (
    <div className="bg-white border border-stone-200 rounded-lg p-5 max-w-2xl space-y-4">
      <div>
        <div className="text-xs font-semibold text-stone-400 uppercase tracking-wide mb-1">
          Formulation classifier {answers.length > 0 && `· ${answers.length} question${answers.length > 1 ? "s" : ""} answered`}
        </div>
        <h3 className="text-base font-semibold text-stone-900">
          {step.done ? "Result" : "Question"}
        </h3>
      </div>

      {!step.done && (
        <div className="space-y-4">
          <p className="text-sm text-stone-800 leading-relaxed">{step.question_text}</p>
          <div className="flex gap-2">
            <button
              onClick={() => answer("yes")}
              className="bg-india text-white text-sm font-medium px-4 py-2 rounded-lg hover:opacity-90"
            >
              Yes
            </button>
            <button
              onClick={() => answer("no")}
              className="bg-stone-200 text-stone-800 text-sm font-medium px-4 py-2 rounded-lg hover:bg-stone-300"
            >
              No
            </button>
          </div>
        </div>
      )}

      {step.done && step.result && (
        <div className="space-y-3">
          <div className="bg-india-light text-india font-semibold text-sm px-3 py-2 rounded-lg inline-block">
            {step.result.category}
          </div>
          <div>
            <div className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">What it requires</div>
            <p className="text-sm text-stone-800">{step.result.requires}</p>
          </div>
          <div>
            <div className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">IP &amp; ABS posture</div>
            <p className="text-sm text-stone-800">{step.result.ip_abs_posture}</p>
          </div>
          <div>
            <div className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">Related sources</div>
            <div className="flex flex-wrap gap-1.5">
              {step.result.relevant_corpus_ids.map((id) => (
                <span key={id} className="text-xs bg-stone-100 text-stone-600 px-2 py-1 rounded font-mono">
                  {id}
                </span>
              ))}
            </div>
          </div>
          <button onClick={restart} className="text-sm text-intl underline">
            Start over
          </button>
        </div>
      )}
    </div>
  );
}
