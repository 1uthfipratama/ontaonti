"use client";

import type { Message } from "@/lib/types";

/** Attachment shown inside a bubble. Placeholder until media download lands. */
export function MessageMedia({ m }: { m: Message }) {
  if (m.kind === "text") return null;
  return <div className="mb-1 text-xs text-muted-foreground">[{m.kind}]</div>;
}
