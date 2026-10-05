"use client";

import { useState } from "react";
import useSWR from "swr";
import { AlertOctagon, AlertTriangle, CheckCircle2 } from "lucide-react";

import { OverviewStrip } from "@/components/overview-strip";
import { ProgrammeCard } from "@/components/programme-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { idr } from "@/lib/format";
import { useT, type T } from "@/lib/i18n";

type Dashboard = {
  timezone: string;
  conversations: {
    today: Record<string, number>;
    month: Record<string, number>;
    daily: { day: string; count: number }[];
  };
  open_cases: { emergency: number; high: number; low: number };
  response_times: {
    bot_median_s: number | null;
    human_median_s: number | null;
    bot_samples: number;
    human_samples: number;
    days: number;
  };
  ai: {
    spent_idr: number;
    budget_idr: number;
    ratio: number;
    alert_ratio: number;
    over: boolean;
    fallback_mode: string;
    by_purpose: Record<string, number>;
    calls: number;
    errors: number;
  };
  whatsapp: { messages_month: number; template_messages_month: number; free_tier: number };
  contacts: { total: number; opted_out: number; subscribed: number };
};

const CHANNEL_LABEL: Record<string, string> = { whatsapp: "WhatsApp", messenger: "Messenger", instagram: "Instagram" };

function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

type Level = "ok" | "warning" | "critical";
const LEVEL: Record<Level, { color: string; icon: React.ReactNode; text: string }> = {
  ok: { color: "var(--viz-seq)", icon: <CheckCircle2 className="size-3.5 text-[var(--viz-good)]" />, text: "dash.ok" },
  warning: { color: "var(--viz-warning)", icon: <AlertTriangle className="size-3.5 text-[var(--viz-warning)]" />, text: "dash.warn" },
  critical: { color: "var(--viz-critical)", icon: <AlertOctagon className="size-3.5 text-[var(--viz-critical)]" />, text: "dash.over" },
};

/** Meter: one ratio against a limit, same-ramp track, optional alert tick. */
function Meter({ id, label, used, limit, alertAt, format, level, note, t }: {
  id: string; label: string; used: number; limit: number; alertAt?: number; format: (n: number) => string; level: Level; note?: string; t: T;
}) {
  const pct = limit > 0 ? Math.min(used / limit, 1) : 0;
  const L = LEVEL[level];
  return (
    <div className="space-y-2" data-testid={`meter-${id}`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-[var(--viz-ink-2)]">{label}</span>
        <span className="text-sm text-[var(--viz-ink)]">
          <b>{format(used)}</b> / {limit > 0 ? format(limit) : t("dash.noLimit")}
        </span>
      </div>
      <div
        className="relative h-2 w-full rounded-full bg-[var(--viz-track)]"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={limit || 1}
        aria-valuenow={used}
        title={`${Math.round(pct * 100)}%`}
      >
        <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, background: L.color }} />
        {alertAt !== undefined && limit > 0 && (
          <div
            className="absolute -top-1 h-[18px] w-px bg-[var(--viz-ink-2)]"
            style={{ left: `${alertAt * 100}%` }}
            title={`${Math.round(alertAt * 100)}%`}
          />
        )}
      </div>
      <div className="flex items-center gap-1 text-xs text-[var(--viz-ink-2)]">
        {L.icon}
        {t(L.text)} · {Math.round(pct * 100)}%{note ? ` · ${note}` : ""}
      </div>
    </div>
  );
}

/** One series, horizontal bars (<=24px, rounded data-end), value at the tip, hover tooltip. */
function Bars({ title, data, table, t }: { title: string; data: { label: string; value: number }[]; table: boolean; t: T }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  if (table) {
    return (
      <table className="w-full text-sm">
        <caption className="mb-1 text-left text-xs text-[var(--viz-ink-2)]">{title}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.label} className="border-b border-[var(--viz-grid)]">
              <td className="py-1">{d.label}</td>
              <td className="py-1 text-right tabular-nums">{d.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  return (
    <figure className="space-y-2">
      <figcaption className="text-xs text-[var(--viz-ink-2)]">{title}</figcaption>
      {data.map((d) => (
        <div key={d.label} className="group grid grid-cols-[5.5rem_1fr] items-center gap-2">
          <span className="text-xs text-[var(--viz-ink-2)]">{d.label}</span>
          <div className="relative flex items-center gap-2 border-l border-[var(--viz-grid)] py-0.5">
            <div
              className="h-4 rounded-r transition-opacity group-hover:opacity-80"
              style={{ width: `${Math.max((d.value / max) * 85, d.value ? 1.5 : 0)}%`, background: "var(--viz-seq)" }}
            />
            <span className="text-xs text-[var(--viz-ink)]">{d.value}</span>
            <span className="pointer-events-none absolute -top-7 left-2 z-10 hidden rounded bg-[var(--viz-ink)] px-2 py-0.5 text-[11px] text-[var(--viz-surface)] group-hover:block">
              {d.label}: {t("dash.conversations", { n: d.value })}
            </span>
          </div>
        </div>
      ))}
    </figure>
  );
}

export default function DashboardPage() {
  const t = useT();
  const { data, error } = useSWR<Dashboard>("/dashboard", { refreshInterval: 30000 });
  const [table, setTable] = useState(false);
  if (error) return <div className="p-6 text-sm text-destructive">{error.message}</div>;
  if (!data) return <div className="p-6 text-sm text-muted-foreground">{t("common.loading")}</div>;

  const series = (k: "today" | "month") =>
    Object.entries(data.conversations[k]).map(([ch, n]) => ({ label: CHANNEL_LABEL[ch] ?? ch, value: n }));
  const sum = (r: Record<string, number>) => Object.values(r).reduce((a, b) => a + b, 0);
  const ai = data.ai;
  const aiLevel: Level = ai.over ? "critical" : ai.budget_idr > 0 && ai.ratio >= ai.alert_ratio ? "warning" : "ok";
  const wa = data.whatsapp;
  const waLevel: Level = wa.template_messages_month >= wa.free_tier ? "critical" : wa.template_messages_month >= wa.free_tier * 0.8 ? "warning" : "ok";

  return (
    <div className="viz-root h-full space-y-4 overflow-y-auto p-6">
      <OverviewStrip
        o={{
          today: sum(data.conversations.today),
          month: sum(data.conversations.month),
          daily: data.conversations.daily,
          botMedian: data.response_times.bot_median_s,
          staffMedian: data.response_times.human_median_s,
          botSamples: data.response_times.bot_samples,
          staffSamples: data.response_times.human_samples,
          contacts: data.contacts,
          cases: data.open_cases,
        }}
      />

      <ProgrammeCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t("dash.costs")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <Meter
              id="ai"
              label={t("dash.aiSpend")}
              used={ai.spent_idr}
              limit={ai.budget_idr}
              alertAt={ai.alert_ratio}
              format={(n) => idr(n)}
              level={aiLevel}
              note={ai.fallback_mode === "fixed_reply" ? t("dash.fallbackFixed") : t("dash.fallbackModel")}
              t={t}
            />
            <div className="text-xs text-[var(--viz-ink-2)]">{t("dash.calls", { n: ai.calls, failed: ai.errors })}</div>
            <Meter
              id="wa"
              label={t("dash.waTemplates")}
              used={wa.template_messages_month}
              limit={wa.free_tier}
              format={(n) => compact(n)}
              level={waLevel}
              note={t("dash.waSent", { n: wa.messages_month })}
              t={t}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center">
            <CardTitle className="flex-1 text-sm">{t("dash.byChannel")}</CardTitle>
            <button className="text-xs font-medium text-primary hover:underline" onClick={() => setTable(!table)}>
              {table ? t("common.chart") : t("common.table")}
            </button>
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-2">
            <Bars title={t("common.today")} data={series("today")} table={table} t={t} />
            <Bars title={t("common.thisMonth")} data={series("month")} table={table} t={t} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
