import type { Answer, Citation } from "./types";

const MARKER = /(\[S\d{1,2}\])/;

function Paragraph({ text, known }: { text: string; known: Set<string> }) {
  const parts = text.split(MARKER);
  return (
    <p>
      {parts.map((part, i) => {
        const label = part.slice(1, -1);
        if (MARKER.test(part) && known.has(label)) {
          return (
            <a key={i} className="cite" href={`#cite-${label}`} aria-label={`Citation ${label}`}>
              {label}
            </a>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </p>
  );
}

function Source({ citation }: { citation: Citation }) {
  const where = citation.page ? `page ${citation.page}` : `§ ${citation.section}`;
  return (
    <li id={`cite-${citation.label}`}>
      <div className="source-head">
        <span className="label">{citation.label}</span>
        <span>
          {citation.source_id}, {where} {citation.heading}
        </span>
        <a href={citation.url} target="_blank" rel="noreferrer noopener">
          Open source
        </a>
      </div>
      <blockquote>{citation.excerpt}</blockquote>
    </li>
  );
}

export function AnswerView({ answer }: { answer: Answer }) {
  if (answer.status !== "answered") {
    const tone = answer.status === "blocked" ? "warn" : "info";
    return <p className={`notice ${tone}`}>{answer.text}</p>;
  }
  const known = new Set(answer.citations.map((c) => c.label));
  const paragraphs = answer.text.split(/\n\s*\n/).filter((p) => p.trim());
  return (
    <article className="answer">
      {paragraphs.map((p, i) => (
        <Paragraph key={i} text={p} known={known} />
      ))}
      <h2>Sources</h2>
      <ol className="sources">
        {answer.citations.map((c) => (
          <Source key={c.label} citation={c} />
        ))}
      </ol>
    </article>
  );
}
