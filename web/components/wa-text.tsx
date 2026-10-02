import { Fragment } from "react";

/** Render WhatsApp formatting (*bold*, _italic_, ~strike~) safely, no HTML injection. */
export function WaText({ text }: { text: string }) {
  const parts = text.split(/(\*[^*\n]+\*|_[^_\n]+_|~[^~\n]+~)/g);
  return (
    <>
      {parts.map((p, i) => {
        if (/^\*[^*\n]+\*$/.test(p)) return <strong key={i}>{p.slice(1, -1)}</strong>;
        if (/^_[^_\n]+_$/.test(p)) return <em key={i}>{p.slice(1, -1)}</em>;
        if (/^~[^~\n]+~$/.test(p)) return <s key={i}>{p.slice(1, -1)}</s>;
        return <Fragment key={i}>{p}</Fragment>;
      })}
    </>
  );
}
