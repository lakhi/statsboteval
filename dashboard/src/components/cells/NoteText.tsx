import { Fragment } from "react";

// A published note is a plain string — contract §6.2 makes a footnote `{ text }` and
// nothing else — so a link inside one has to be *recognised*, not marked up. That is the
// point: no markup ever enters the blob, and no blob text is ever handed to
// dangerouslySetInnerHTML. React elements only, which makes rendering published prose
// safe by construction rather than by review (D-58).
const URL_PATTERN = /(https?:\/\/[^\s]+)/g;
// A URL ending a sentence otherwise swallows the period into the href.
const TRAILING_PUNCTUATION = /[.,;:!?)\]]+$/;

/** Note prose with bare URLs rendered as links. */
export function NoteText({ text }: { text: string }) {
  // split() with a capturing group alternates non-match / match, so odd indices are URLs.
  const parts = text.split(URL_PATTERN);
  return (
    <>
      {parts.map((part, i) => {
        if (i % 2 === 0) return <Fragment key={i}>{part}</Fragment>;
        const trailing = TRAILING_PUNCTUATION.exec(part)?.[0] ?? "";
        const href = trailing ? part.slice(0, -trailing.length) : part;
        return (
          <Fragment key={i}>
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-accent underline decoration-hairline underline-offset-2 transition-colors hover:text-accent-deep hover:decoration-accent"
            >
              {href}
            </a>
            {trailing}
          </Fragment>
        );
      })}
    </>
  );
}
