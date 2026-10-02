"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { AlertOctagon, AlertTriangle, CheckCircle2, Info } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { idr } from "@/lib/format";

type Dashboard = {
  timezone: string;
  conversations: { today: Record<string, number>; month: Record<string, number> };
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

function duration(s: number | null): string {
  if (s === null) return "—";
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${(s / 60).toFixed(1)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

/** Stat tile: label, value, optional sub-line. */
function Tile({ label, value, sub, icon, testId }: { label: string; value: string; sub?: string; icon?: React.ReactNode; testId?: string }) {
  return (
    <div className="rounded-xl border bg-[var(--viz-surface)] p-4" data-testid={testId}>
      <div className="flex items-center gap-1.5 text-xs text-[var(--viz-ink-2)]">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-[var(--viz-ink)]">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-[var(--viz-muted)]">{sub}</div>}
    </div>
  );
}

type Level = "ok" | "warning" | "critical";
const LEVEL: Record<Level, { color: string; icon: React.ReactNode; text: string }> = {
  ok: { color: "var(--viz-seq)", icon: <CheckCircle2 className="size-3.5 text-[var(--viz-good)]" />, text: "Within limit" },
  warning: { color: "var(--viz-warning)", icon: <AlertTriangle className="size-3.5 text-[var(--viz-warning)]" />, text: "Approaching limit" },
  critical: { color: "var(--viz-critical)", icon: <AlertOctagon className="size-3.5 text-[var(--viz-critical)]" />, text: "Limit reached" },
};

/** Meter: one ratio against a limit, same-ramp track, optional alert tick. */
function Meter({ label, used, limit, alertAt, format, level, note }: {
  label: string; used: number; limit: number; alertAt?: number; format: (n: number) => string; level: Level; note?: string;
}) {
  const pct = limit > 0 ? Math.min(used / limit, 1) : 0;
  const L = LEVEL[level];
  return (
    <div className="space-y-2" data-testid={`meter-${label}`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-[var(--viz-ink-2)]">{label}</span>
        <span className="text-sm text-[var(--viz-ink)]">
          <b>{format(used)}</b> / {limit > 0 ? format(limit) : "no limit"}
        </span>
      </div>
      <div
        className="relative h-2.5 w-full rounded-full bg-[var(--viz-track)]"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={limit || 1}
        aria-valuenow={used}
        title={`${format(used)} of ${limit > 0 ? format(limit) : "no limit"} (${Math.round(pct * 100)}%)`}
      >
        <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, background: L.color }} />
        {alertAt !== undefined && limit > 0 && (
          <div
            className="absolute -top-1 h-[18px] w-px bg-[var(--viz-ink-2)]"
            style={{ left: `${alertAt * 100}%` }}
            title={`Alert at ${Math.round(alertAt * 100)}%`}
          />
        )}
      </div>
      <div className="flex items-center gap-1 text-xs text-[var(--viz-ink-2)]">
        {L.icon}
        {L.text} · {Math.round(pct * 100)}%{note ? ` · ${note}` : ""}
      </div>
    </div>
  );
}

/** One series, horizontal bars (<=24px, rounded data-end), value at the tip, hover tooltip. */
function Bars({ title, data, table }: { title: string; data: { label: string; value: number }[]; table: boolean }) {
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
              {d.label}: {d.value} conversation{d.value === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      ))}
    </figure>
  );
}

export default function DashboardPage() {
  const { data, error } = useSWR<Dashboard>("/dashboard", { refreshInterval: 30000 });
  const [table, setTable] = useState(false);
  if (error) return <div className="p-6 text-sm text-red-600">{error.message}</div>;
  if (!data) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;

  const series = (k: "today" | "month") =>
    Object.entries(data.conversations[k]).map(([ch, n]) => ({ label: CHANNEL_LABEL[ch] ?? ch, value: n }));
  const todayTotal = Object.values(data.conversations.today).reduce((a, b) => a + b, 0);
  const ai = data.ai;
  const aiLevel: Level = ai.over ? "critical" : ai.budget_idr > 0 && ai.ratio >= ai.alert_ratio ? "warning" : "ok";
  const wa = data.whatsapp;
  const waLevel: Level = wa.template_messages_month >= wa.free_tier ? "critical" : wa.template_messages_month >= wa.free_tier * 0.8 ? "warning" : "ok";
  const cases = data.open_cases;

  return (
    <div className="viz-root h-full space-y-6 overflow-y-auto p-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-lg font-semibold">Dashboard</h1>
        <span className="text-xs text-muted-foreground">Days and months in {data.timezone}</span>
      </div>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Key figures">
        <Tile label="Conversations today" value={compact(todayTotal)} sub={`${compact(Object.values(data.conversations.month).reduce((a, b) => a + b, 0))} this month`} testId="tile-today" />
        <Tile label="Median first response · bot" value={duration(data.response_times.bot_median_s)} sub={`${data.response_times.bot_samples} replies, last ${data.response_times.days} days`} />
        <Tile label="Median first response · human" value={duration(data.response_times.human_median_s)} sub={`${data.response_times.human_samples} replies, last ${data.response_times.days} days`} />
        <Tile label="Contacts" value={compact(data.contacts.total)} sub={`${data.contacts.subscribed} subscribed · ${data.contacts.opted_out} opted out`} />
      </section>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3" aria-label="Open cases by severity">
        <Link href="/cases">
          <Tile label="Open cases · emergency" value={String(cases.emergency)} icon={<AlertOctagon className="size-3.5 text-[var(--viz-critical)]" />} testId="tile-emergency" />
        </Link>
        <Link href="/cases">
          <Tile label="Open cases · high" value={String(cases.high)} icon={<AlertTriangle className="size-3.5 text-[var(--viz-serious)]" />} />
        </Link>
        <Link href="/cases">
          <Tile label="Open cases · low" value={String(cases.low)} icon={<Info className="size-3.5 text-[var(--viz-warning)]" />} />
        </Link>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Costs this month</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <Meter
              label="AI spend vs budget"
              used={ai.spent_idr}
              limit={ai.budget_idr}
              alertAt={ai.alert_ratio}
              format={(n) => idr(n)}
              level={aiLevel}
              note={`at 100%: ${ai.fallback_mode === "fixed_reply" ? "fixed reply + case" : "cheaper classifier model"}`}
            />
            <div className="text-xs text-[var(--viz-ink-2)]">
              {ai.calls} LLM calls ({ai.errors} failed) ·{" "}
              {Object.entries(ai.by_purpose).map(([k, v]) => `${k} ${idr(v)}`).join(" · ") || "no spend yet"}
            </div>
            <Meter
              label="WhatsApp template messages vs free tier"
              used={wa.template_messages_month}
              limit={wa.free_tier}
              format={(n) => compact(n)}
              level={waLevel}
              note={`${wa.messages_month} WhatsApp messages sent in total`}
            />
            <p className="text-[11px] text-muted-foreground">
              Free-tier size and per-message rates are settings (Settings → WhatsApp pricing); check Meta&apos;s current rate card.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center">
            <CardTitle className="flex-1 text-sm">Active conversations by channel</CardTitle>
            <button className="text-xs text-primary hover:underline" onClick={() => setTable(!table)}>
              {table ? "Show bars" : "Show table"}
            </button>
          </CardHeader>
          <CardContent className="grid gap-6 sm:grid-cols-2">
            <Bars title="Today" data={series("today")} table={table} />
            <Bars title="This month" data={series("month")} table={table} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
