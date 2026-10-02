"use client";

import useSWR from "swr";

import { ChannelBadge, ModeBadge, SeverityBadge } from "@/components/badges";
import { NativeSelect } from "@/components/native-select";
import { Input } from "@/components/ui/input";
import { timeAgo } from "@/lib/format";
import type { Conversation } from "@/lib/types";
import { cn } from "@/lib/utils";

export type Filters = { channel: string; status: string; flag: string; mode: string; q: string };

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
  const params = new URLSearchParams(
    Object.entries(filters).filter(([, v]) => v) as [string, string][],
  ).toString();
  const { data, error } = useSWR<Conversation[]>(`/conversations?${params}`);
  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) =>
    setFilters({ ...filters, [k]: e.target.value });

  return (
    <div className="flex h-full flex-col border-r">
      <div className="space-y-2 border-b p-3">
        <Input placeholder="Search name or text…" value={filters.q} onChange={set("q")} className="h-8" />
        <div className="grid grid-cols-2 gap-2">
          <NativeSelect
            aria-label="Channel"
            value={filters.channel}
            onChange={set("channel")}
            options={[
              { value: "", label: "All channels" },
              { value: "whatsapp", label: "WhatsApp" },
              { value: "messenger", label: "Messenger" },
              { value: "instagram", label: "Instagram" },
            ]}
          />
          <NativeSelect
            aria-label="Status"
            value={filters.status}
            onChange={set("status")}
            options={[
              { value: "", label: "Any status" },
              { value: "OPEN", label: "Open" },
              { value: "RESOLVED", label: "Resolved" },
            ]}
          />
          <NativeSelect
            aria-label="Flag"
            value={filters.flag}
            onChange={set("flag")}
            options={[
              { value: "", label: "Any flag" },
              { value: "flagged", label: "Flagged" },
              { value: "high", label: "High+" },
              { value: "emergency", label: "Emergency" },
            ]}
          />
          <NativeSelect
            aria-label="Mode"
            value={filters.mode}
            onChange={set("mode")}
            options={[
              { value: "", label: "Bot + human" },
              { value: "BOT", label: "Bot" },
              { value: "HUMAN", label: "Human" },
            ]}
          />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto" data-testid="conversation-list">
        {error && <p className="p-3 text-sm text-red-600">{error.message}</p>}
        {data?.length === 0 && <p className="p-3 text-sm text-muted-foreground">No conversations.</p>}
        {data?.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            data-testid="conversation-item"
            className={cn(
              "block w-full border-b px-3 py-2 text-left hover:bg-muted/60",
              selected === c.id && "bg-muted",
              c.flag_severity === "emergency" && "border-l-4 border-l-red-600",
              c.flag_severity === "high" && "border-l-4 border-l-orange-500",
            )}
          >
            <div className="flex items-center gap-2">
              <span className={cn("flex-1 truncate text-sm", c.unread_count > 0 && "font-semibold")}>
                {c.contact_name || c.identity?.external_id}
              </span>
              <span className="text-[11px] text-muted-foreground">{timeAgo(c.last_message_at)}</span>
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">{c.last_preview}</div>
            <div className="mt-1 flex flex-wrap items-center gap-1">
              <ChannelBadge channel={c.channel} simulated={c.simulated} />
              <ModeBadge mode={c.mode} />
              <SeverityBadge severity={c.flag_severity} />
              {c.status === "RESOLVED" && (
                <span className="rounded bg-muted px-1.5 py-0.5 text-[11px]">resolved</span>
              )}
              {c.opted_out && <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[11px] text-white">STOP</span>}
              {c.unread_count > 0 && (
                <span className="ml-auto rounded-full bg-primary px-1.5 text-[11px] text-primary-foreground">
                  {c.unread_count}
                </span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
