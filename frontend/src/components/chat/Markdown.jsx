import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Turn "[3]" into a link the renderer below draws as a citation chip.
const withCitationLinks = (text) => text.replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)");

export default function Markdown({ text, onCite, maxRef }) {
  return (
    <div className="prose-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const m = href?.match(/^#cite-(\d+)$/);
            if (m) {
              const n = Number(m[1]);
              if (n < 1 || n > maxRef) return null;
              return (
                <button
                  type="button"
                  onClick={() => onCite?.(n)}
                  className="mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md bg-primary-soft px-1 align-middle font-mono text-[10.5px] font-medium text-primary transition hover:bg-primary hover:text-primary-ink"
                  aria-label={`Source ${n}`}
                >
                  {n}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {withCitationLinks(text)}
      </ReactMarkdown>
    </div>
  );
}
