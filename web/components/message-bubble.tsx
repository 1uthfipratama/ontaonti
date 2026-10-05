"use client";

import { cn } from "@/lib/utils";
import { clock, idr } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { Message } from "@/lib/types";
import { SeverityBadge } from "@/components/badges";
import { MessageMedia } from "@/components/message-media";
import { WaText } from "@/components/wa-text";

export function MessageBubble({ m, staffName }: { m: Message; staffName?: string }) {
  const t = useT();

  // System notes (mode changes, handovers): one quiet centred line.
  if (m.direction === "note" && m.sender_type === "system") {
    return (
      <div className="my-3 text-center text-xs text-muted-foreground" data-testid="note">
        {m.text} · {clock(m.created_at)}
      </div>
    );
  }
  // Staff notes: internal, never sent. Full width, set apart by a left rule.
  if (m.direction === "note") {
    return (
      <div className="my-3 border-l-2 border-[var(--sev-low)] bg-muted px-3 py-2" data-testid="staff-note">
        <div className="mb-0.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">{t("msg.note")}</span>
          {staffName && ` · ${staffName}`} · {clock(m.created_at)}
        </div>
        <div className="whitespace-pre-wrap break-words text-sm">{m.text}</div>
      </div>
    );
  }

  const inbound = m.direction === "in";
  const sources = (m.meta?.sources as { doc: string }[] | undefined) ?? [];
  const labels: Record<string, string> = {
    user: "",
    bot: t("msg.bot"),
    agent: staffName || t("msg.staff"),
    system: t("msg.broadcast"),
  };
  return (
    <div className={cn("my-2 flex flex-col", inbound ? "items-start" : "items-end")}>
      <div className="mb-1 flex items-center gap-2 px-1 text-xs text-muted-foreground">
        {labels[m.sender_type] && <span className="font-medium text-foreground/80">{labels[m.sender_type]}</span>}
        <span>{clock(m.created_at)}</span>
        {!inbound && m.status !== "sent" && <span>· {m.status}</span>}
        <SeverityBadge severity={m.flag_severity} category={m.flag_category} />
      </div>
      <div
        data-testid={`bubble-${m.sender_type}`}
        className={cn(
          "max-w-[75%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed",
          inbound ? "bg-secondary" : "bg-accent",
        )}
      >
        <MessageMedia m={m} />
        {m.text && (
          <div className="whitespace-pre-wrap break-words">
            <WaText text={m.text} />
          </div>
        )}
      </div>
      {m.error && <div className="mt-1 px-1 text-xs text-destructive">{t("msg.notDelivered", { error: m.error })}</div>}
      {m.flag_reason && inbound && (
        <div className="mt-1 px-1 text-xs text-muted-foreground">{t("msg.flaggedBy", { reason: m.flag_reason })}</div>
      )}
      {(sources.length > 0 || m.tokens_out > 0) && (
        <div className="mt-1 px-1 text-[11px] text-subtle-foreground">
          {sources.length > 0 && <>{t("msg.sources", { docs: sources.map((s) => s.doc).join(", ") })} · </>}
          {t("msg.tokens", { n: m.tokens_in + m.tokens_out })} · {idr(m.cost_idr, 2)}
        </div>
      )}
    </div>
  );
}
