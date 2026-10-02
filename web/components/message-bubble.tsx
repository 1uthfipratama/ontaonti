import { cn } from "@/lib/utils";
import { clock, idr } from "@/lib/format";
import type { Message } from "@/lib/types";
import { SeverityBadge } from "@/components/badges";
import { WaText } from "@/components/wa-text";

const SENDER_LABEL: Record<string, string> = { user: "", bot: "Onti (bot)", agent: "Staff", system: "Broadcast" };

export function MessageBubble({ m, staffName }: { m: Message; staffName?: string }) {
  if (m.direction === "note") {
    return (
      <div className="my-3 text-center text-xs text-muted-foreground" data-testid="note">
        {m.text} · {clock(m.created_at)}
      </div>
    );
  }
  const inbound = m.direction === "in";
  const sources = (m.meta?.sources as { doc: string }[] | undefined) ?? [];
  const who = m.sender_type === "agent" && staffName ? staffName : SENDER_LABEL[m.sender_type];
  return (
    <div className={cn("my-2 flex flex-col", inbound ? "items-start" : "items-end")}>
      <div className="mb-1 flex items-center gap-2 px-1 text-xs text-muted-foreground">
        {who && <span className="font-medium text-foreground/80">{who}</span>}
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
        {m.kind !== "text" && <div className="mb-1 text-xs text-muted-foreground">[{m.kind}]</div>}
        <div className="whitespace-pre-wrap break-words">
          <WaText text={m.text} />
        </div>
      </div>
      {m.error && <div className="mt-1 px-1 text-xs text-destructive">Not delivered: {m.error}</div>}
      {m.flag_reason && inbound && <div className="mt-1 px-1 text-xs text-muted-foreground">Flagged by {m.flag_reason}</div>}
      {(sources.length > 0 || m.tokens_out > 0) && (
        <div className="mt-1 px-1 text-[11px] text-muted-foreground">
          {sources.length > 0 && <>Sources {sources.map((s) => s.doc).join(", ")} · </>}
          {m.tokens_in + m.tokens_out} tokens · {idr(m.cost_idr, 2)}
        </div>
      )}
    </div>
  );
}
