import { cn } from "@/lib/utils";
import { clock, idr } from "@/lib/format";
import type { Message } from "@/lib/types";
import { SeverityBadge } from "@/components/badges";
import { WaText } from "@/components/wa-text";

const SENDER_LABEL: Record<string, string> = { user: "User", bot: "Onti (bot)", agent: "Staff", system: "System" };

export function MessageBubble({ m, staffName }: { m: Message; staffName?: string }) {
  if (m.direction === "note") {
    return (
      <div className="my-2 text-center text-[11px] italic text-muted-foreground" data-testid="note">
        {m.text} · {clock(m.created_at)}
      </div>
    );
  }
  const inbound = m.direction === "in";
  const sources = (m.meta?.sources as { doc: string; heading: string }[] | undefined) ?? [];
  return (
    <div className={cn("my-1.5 flex", inbound ? "justify-start" : "justify-end")}>
      <div
        data-testid={`bubble-${m.sender_type}`}
        className={cn(
          "max-w-[78%] rounded-2xl px-3 py-2 text-sm shadow-sm",
          inbound && "rounded-bl-sm bg-muted",
          m.sender_type === "bot" && "rounded-br-sm bg-violet-100 dark:bg-violet-950",
          m.sender_type === "agent" && "rounded-br-sm bg-emerald-100 dark:bg-emerald-950",
          m.sender_type === "system" && !inbound && "rounded-br-sm bg-sky-100 dark:bg-sky-950",
          m.status === "failed" && "ring-2 ring-red-500",
        )}
      >
        <div className="mb-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="font-medium">
            {m.sender_type === "agent" && staffName ? staffName : SENDER_LABEL[m.sender_type]}
          </span>
          <span>{clock(m.created_at)}</span>
          {!inbound && <span>· {m.status}</span>}
          <SeverityBadge severity={m.flag_severity} category={m.flag_category} />
        </div>
        {m.kind !== "text" && (
          <div className="mb-1 text-xs font-medium text-muted-foreground">[{m.kind}]</div>
        )}
        <div className="whitespace-pre-wrap break-words">
          <WaText text={m.text} />
        </div>
        {m.flag_reason && <div className="mt-1 text-[11px] text-orange-700 dark:text-orange-300">⚑ {m.flag_reason}</div>}
        {m.error && <div className="mt-1 text-[11px] text-red-600">Not delivered: {m.error}</div>}
        {(sources.length > 0 || m.tokens_out > 0) && (
          <div className="mt-1 text-[10px] text-muted-foreground">
            {sources.length > 0 && <>Sources: {sources.map((s) => s.doc).join(", ")} · </>}
            {m.tokens_in}+{m.tokens_out} tok · {idr(m.cost_idr, 2)}
          </div>
        )}
      </div>
    </div>
  );
}
