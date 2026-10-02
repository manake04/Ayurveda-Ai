import { useCallback, useRef, useState } from "react";
import { streamAnswer } from "../lib/api.js";

let nextId = 1;

function emptyBlock(jurisdiction) {
  return { jurisdiction, status: "retrieving", answer: "", citations: [], related: [] };
}

/** Conversation state plus a `send` that streams the answer into it. */
export function useChat() {
  const [turns, setTurns] = useState([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef(null);

  const update = (id, fn) => setTurns((prev) => prev.map((t) => (t.id === id ? fn(t) : t)));
  const updateBlock = (id, jurisdiction, fn) =>
    update(id, (t) => ({ ...t, blocks: { ...t.blocks, [jurisdiction]: fn(t.blocks[jurisdiction]) } }));

  const send = useCallback(async ({ query, jurisdiction, language }) => {
    const id = nextId++;
    const order = jurisdiction === "both" ? ["india", "international"] : [jurisdiction];
    setTurns((prev) => [
      ...prev,
      {
        id,
        query,
        jurisdiction,
        language,
        order,
        blocks: Object.fromEntries(order.map((j) => [j, emptyBlock(j)])),
        error: null,
        latencyMs: null,
      },
    ]);
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamAnswer(
        { query, jurisdiction, language },
        (event) => {
          if (event.type === "sources") {
            const { type, ...rest } = event;
            updateBlock(id, event.jurisdiction, (b) => ({ ...b, ...rest, status: "writing" }));
          } else if (event.type === "delta") {
            updateBlock(id, event.jurisdiction, (b) => ({ ...b, answer: b.answer + event.text }));
          } else if (event.type === "done") {
            updateBlock(id, event.jurisdiction, (b) => ({
              ...b,
              answer: event.answer,
              generatedBy: event.generated_by,
              status: "done",
            }));
          } else if (event.type === "end") {
            update(id, (t) => ({ ...t, latencyMs: event.latency_ms }));
          }
        },
        controller.signal,
      );
    } catch (err) {
      const aborted = err.name === "AbortError";
      update(id, (t) => ({
        ...t,
        error: aborted ? null : err.message,
        blocks: Object.fromEntries(
          Object.entries(t.blocks).map(([j, b]) => [j, b.status === "done" ? b : { ...b, status: aborted ? "stopped" : "error" }]),
        ),
      }));
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }, []);

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const reset = useCallback(() => {
    abortRef.current?.abort();
    setTurns([]);
  }, []);

  return { turns, busy, send, stop, reset };
}
