"use client";

import { useT } from "@/lib/i18n";
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
  const t = useT();
  return (
    <span className="text-xs text-muted-foreground">
      {channelName(channel)}
      {simulated && ` · ${t("common.simulated")}`}
    </span>
  );
}

const SEV_COLOR: Record<Severity, string> = {
  none: "",
  low: "bg-[var(--sev-low)]",
  high: "bg-[var(--sev-high)]",
  emergency: "bg-[var(--sev-emergency)]",
};

export function SeverityDot({ severity, className }: { severity: Severity | null; className?: string }) {
  if (!severity || severity === "none") return null;
  return <span className={cn("inline-block size-2 shrink-0 rounded-full", SEV_COLOR[severity], className)} aria-hidden />;
}

/** Translated category ("ADVERSE_DRUG" -> "efek samping obat"); "" when it adds nothing. */
export function useCategory() {
  const t = useT();
  return (category: string | null | undefined, severity?: string | null) => {
    if (!category) return "";
    const key = `cat.${category.toLowerCase()}`;
    const label = t(key);
    if (label === key) return category === "OTHER" || category === "NONE" ? "" : category.toLowerCase().replace("_", " ");
    return label === t(`sev.${severity}`).toLowerCase() ? "" : label;
  };
}

export function SeverityBadge({ severity, category }: { severity: Severity | null; category?: string | null }) {
  const t = useT();
  const cat = useCategory()(category, severity);
  if (!severity || severity === "none") return null;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-foreground">
      <SeverityDot severity={severity} />
      {t(`sev.${severity}`)}
      {cat && <span className="font-normal text-muted-foreground">· {cat}</span>}
    </span>
  );
}

/** Only HUMAN mode is worth calling out; bot mode is the default. */
export function ModeBadge({ mode }: { mode: "BOT" | "HUMAN" }) {
  const t = useT();
  if (mode !== "HUMAN") return null;
  return <span className="text-xs font-medium text-primary">{t("mode.human")}</span>;
}
