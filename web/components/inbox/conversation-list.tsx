"use client";

import useSWR from "swr";
import { Search } from "lucide-react";

import { channelName, SeverityDot } from "@/components/badges";
import { NativeSelect } from "@/components/native-select";
import { Input } from "@/components/ui/input";
import { timeAgo } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { Conversation, LabelRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export type Filters = { channel: string; status: string; flag: string; mode: string; label: string; q: string };

export function ConversationList({
  filters,
  setFilters,
  selected,
  onSelect,
}: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  selected: number | null;
  onSelect: (id: number) => void;
}) {
  const t = useT();
  const params = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v) as [string, string][],
  ).toString();
  const { data, error } = useSWR<Conversation[]>(`/conversations?${params}`);
  const { data: labels } = useSWR<LabelRef[]>("/labels");
  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) =>
    setFilters({ ...filters, [k]: e.target.value });

  return (
    <div className="flex h-full flex-col border-r border-border bg-card">
      <div className="space-y-2 p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground" />
          <Input placeholder={t("inbox.searchPlaceholder")} value={filters.q} onChange={set("q")} className="pl-9" />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <NativeSelect
            aria-label={t("inbox.filterChannel")}
            value={filters.channel}
            onChange={set("channel")}
            options={[
              { value: "", label: t("inbox.allChannels") },
              { value: "whatsapp", label: "WhatsApp" },
              { value: "messenger", label: "Messenger" },
              { value: "instagram", label: "Instagram" },
            ]}
          />
          <NativeSelect
            aria-label={t("inbox.filterStatus")}
            value={filters.status}
            onChange={set("status")}
            options={[
              { value: "", label: t("inbox.anyStatus") },
              { value: "OPEN", label: t("inbox.open") },
              { value: "RESOLVED", label: t("inbox.resolved") },
            ]}
          />
          <NativeSelect
            aria-label={t("inbox.filterFlag")}
            value={filters.flag}
            onChange={set("flag")}
            options={[
              { value: "", label: t("inbox.anyFlag") },
              { value: "flagged", label: t("inbox.flagged") },
              { value: "high", label: t("inbox.highUp") },
              { value: "emergency", label: t("inbox.emergency") },
            ]}
          />
          <NativeSelect
            aria-label={t("inbox.filterMode")}
            value={filters.mode}
            onChange={set("mode")}
            options={[
              { value: "", label: t("inbox.botAndStaff") },
              { value: "BOT", label: t("inbox.bot") },
              { value: "HUMAN", label: t("inbox.staffHandling") },
            ]}
          />
          {(labels?.length ?? 0) > 0 && (
            <NativeSelect
              aria-label={t("inbox.filterLabel")}
              className="col-span-2"
              value={filters.label}
              onChange={set("label")}
              options={[
                { value: "", label: t("inbox.anyLabel") },
                ...(labels ?? []).map((l) => ({ value: String(l.id), label: l.name })),
              ]}
            />
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-2" data-testid="conversation-list">
        {error && <p className="p-3 text-sm text-destructive">{error.message}</p>}
        {data?.length === 0 && <p className="p-3 text-sm text-muted-foreground">{t("inbox.empty")}</p>}
        {data?.map((c) => {
          const meta = [
            channelName(c.channel) + (c.simulated ? ` (${t("channel.simulated")})` : ""),
            c.mode === "HUMAN" ? t("inbox.staffHandling") : "",
            c.status === "RESOLVED" ? t("inbox.resolved") : "",
            c.opted_out ? t("inbox.optedOut") : "",
            ...c.labels.map((l) => l.name),
          ].filter(Boolean);
          return (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              data-testid="conversation-item"
              className={cn(
                "block w-full rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted",
                selected === c.id && "bg-accent hover:bg-accent",
              )}
            >
              <div className="flex items-center gap-2">
                <SeverityDot severity={c.flag_severity} />
                <span className={cn("flex-1 truncate text-sm", c.unread_count > 0 ? "font-semibold" : "font-medium")}>
                  {c.contact_name || c.identity?.external_id}
                </span>
                <span className="text-xs text-muted-foreground">{timeAgo(c.last_message_at, t)}</span>
              </div>
              <div className="mt-0.5 flex items-center gap-2">
                <span className={cn("flex-1 truncate text-[13px]", c.unread_count > 0 ? "text-foreground" : "text-muted-foreground")}>
                  {c.last_preview}
                </span>
                {c.unread_count > 0 && (
                  <span className="min-w-5 rounded-full bg-primary px-1.5 text-center text-[11px] font-semibold leading-5 text-primary-foreground">
                    {c.unread_count}
                  </span>
                )}
              </div>
              <div className="mt-0.5 truncate text-xs text-muted-foreground">{meta.join(" · ")}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
