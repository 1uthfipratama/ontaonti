import { cn } from "@/lib/utils";
import type { Channel, Severity } from "@/lib/types";

const CHANNEL_STYLE: Record<Channel, string> = {
  whatsapp: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  messenger: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200",
  instagram: "bg-pink-100 text-pink-800 dark:bg-pink-900/40 dark:text-pink-200",
};
const CHANNEL_LABEL: Record<Channel, string> = {
  whatsapp: "WhatsApp",
  messenger: "Messenger",
  instagram: "Instagram",
};

export function ChannelBadge({ channel, simulated }: { channel: Channel; simulated?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium",
        CHANNEL_STYLE[channel],
      )}
    >
      {CHANNEL_LABEL[channel] ?? channel}
      {simulated && <span className="rounded bg-black/10 px-1 text-[10px] dark:bg-white/15">SIM</span>}
    </span>
  );
}

const SEV_STYLE: Record<Severity, string> = {
  none: "bg-muted text-muted-foreground",
  low: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  high: "bg-orange-200 text-orange-900 dark:bg-orange-900/50 dark:text-orange-100",
  emergency: "bg-red-600 text-white",
};

export function SeverityBadge({ severity, category }: { severity: Severity | null; category?: string | null }) {
  if (!severity || severity === "none") return null;
  return (
    <span className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase", SEV_STYLE[severity])}>
      {severity}
      {category ? ` · ${category.replace("_", " ")}` : ""}
    </span>
  );
}

export function ModeBadge({ mode }: { mode: "BOT" | "HUMAN" }) {
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 text-[11px] font-medium",
        mode === "BOT"
          ? "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200"
          : "bg-yellow-100 text-yellow-900 dark:bg-yellow-900/40 dark:text-yellow-100",
      )}
    >
      {mode === "BOT" ? "Bot" : "Human"}
    </span>
  );
}
