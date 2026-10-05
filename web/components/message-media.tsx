"use client";

import { FileText } from "lucide-react";

import { API_URL } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Message } from "@/lib/types";

/** URL of a stored file ("media:<name>"), or null when the file isn't stored. */
export function mediaSrc(m: Pick<Message, "media_url">): string | null {
  return m.media_url?.startsWith("media:") ? `${API_URL}/media/${m.media_url.slice(6)}` : null;
}

/** True when the bubble text is only a "[gambar]"-style label for the file. */
export function textIsPlaceholder(m: Message): boolean {
  return Boolean(m.meta?.placeholder) && !m.meta?.transcript;
}

/** Attachment shown inside a bubble: image, player, or a file link. */
export function MessageMedia({ m }: { m: Message }) {
  const t = useT();
  if (m.kind === "text") return null;
  const src = mediaSrc(m);
  if (!src) return null; // not downloaded (simulator, expired link): the text label stands in
  const name = (m.meta?.filename as string | undefined) ?? t("msg.openFile");

  switch (m.kind) {
    case "image":
    case "sticker":
      return (
        <a href={src} target="_blank" rel="noreferrer" className="mb-1.5 block">
          {/* eslint-disable-next-line @next/next/no-img-element -- private API file, not optimisable */}
          <img
            src={src}
            alt=""
            className={m.kind === "sticker" ? "size-28 object-contain" : "max-h-72 max-w-full rounded-md object-cover"}
          />
        </a>
      );
    case "audio":
      return (
        <div className="mb-1.5">
          <audio controls preload="none" src={src} className="h-9 w-64 max-w-full" />
          {Boolean(m.meta?.transcript) && (
            <div className="mt-1.5 text-[11px] font-medium text-muted-foreground">{t("msg.transcript")}</div>
          )}
        </div>
      );
    case "video":
      return <video controls preload="metadata" src={src} className="mb-1.5 max-h-72 max-w-full rounded-md" />;
    default:
      return (
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          className="mb-1.5 flex items-center gap-2 rounded-md bg-card/70 px-2.5 py-2 hover:bg-card"
        >
          <FileText className="size-5 shrink-0 text-primary" />
          <span className="truncate font-medium">{name}</span>
        </a>
      );
  }
}
