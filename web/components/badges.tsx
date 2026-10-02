import { cn } from "@/lib/utils";
import type { Channel, Severity } from "@/lib/types";

/* Quiet labels instead of coloured pills: channel, mode and status are plain
   secondary text. Only a real risk flag gets colour (a small dot). */

const CHANNEL_LABEL: Record<Channel, string> = {
  whatsapp: "WhatsApp",
  messenger: "Messenger",
  instagram: "Instagram",
};

export function channelName(channel: Channel): string {
  return CHANNEL_LABEL[channel] ?? channel;
}

export function ChannelBadge({ channel, simulated }: { channel: Channel; simulated?: boolean }) {
  return (
    <span className="text-xs text-muted-foreground">
      {channelName(channel)}
      {simulated && " · simulated"}
    </span>
  );
}

const SEV_COLOR: Record<Severity, string> = {
  none: "",
  low: "bg-[var(--sev-low)]",
  high: "bg-[var(--sev-high)]",
  emergency: "bg-[var(--sev-emergency)]",
};
const SEV_LABEL: Record<Severity, string> = { none: "", low: "Low", high: "High", emergency: "Emergency" };

export function SeverityDot({ severity, className }: { severity: Severity | null; className?: string }) {
  if (!severity || severity === "none") return null;
  return <span className={cn("inline-block size-2 shrink-0 rounded-full", SEV_COLOR[severity], className)} aria-hidden />;
}

export function SeverityBadge({ severity, category }: { severity: Severity | null; category?: string | null }) {
  if (!severity || severity === "none") return null;
  let cat = category ? category.toLowerCase().replace("_", " ") : "";
  if (cat === severity || cat === "other" || cat === "none") cat = "";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground">
      <SeverityDot severity={severity} />
      {SEV_LABEL[severity]}
      {cat && <span className="font-normal text-muted-foreground">· {cat}</span>}
    </span>
  );
}

/** Only HUMAN mode is worth calling out; bot mode is the default. */
export function ModeBadge({ mode }: { mode: "BOT" | "HUMAN" }) {
  if (mode !== "HUMAN") return null;
  return <span className="text-xs font-medium text-primary">Staff handling</span>;
}
