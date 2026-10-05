"use client";

import Link from "next/link";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type Overview = {
  today: number;
  month: number;
  daily: { day: string; count: number }[];
  botMedian: number | null;
  staffMedian: number | null;
  botSamples: number;
  staffSamples: number;
  contacts: { total: number; subscribed: number; opted_out: number };
  cases: { emergency: number; high: number; low: number };
};

function duration(s: number | null): string {
  if (s === null) return "—";
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${(s / 60).toFixed(1)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="text-xs text-[var(--viz-ink-2)]">{children}</div>;
}

function Big({ children }: { children: React.ReactNode }) {
  return <div className="text-2xl font-semibold leading-tight text-[var(--viz-ink)] tabular-nums">{children}</div>;
}

/** 14 daily columns; today in full colour, hover for the value. */
function DailyColumns({ daily }: { daily: Overview["daily"] }) {
  const t = useT();
  const max = Math.max(1, ...daily.map((d) => d.count));
  return (
    <div className="flex h-10 items-end gap-[3px]" role="img" aria-label={t("dash.last14")}>
      {daily.map((d, i) => (
        <div
          key={d.day}
          title={`${new Date(d.day + "T00:00:00").toLocaleDateString("id-ID", { day: "numeric", month: "short" })}: ${d.count}`}
          className={cn("w-1.5 rounded-t-sm", i === daily.length - 1 ? "bg-[var(--viz-seq)]" : "bg-[var(--viz-seq)] opacity-35")}
          style={{ height: `${Math.max((d.count / max) * 100, d.count ? 8 : 4)}%` }}
        />
      ))}
    </div>
  );
}

/** One bar split into parts; each part's width is its share of `total`. */
function SplitBar({ parts, total }: { parts: { value: number; color: string; label: string }[]; total: number }) {
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-[var(--viz-track)]">
      {parts.map((p) =>
        p.value > 0 ? (
          <div key={p.label} title={`${p.label}: ${p.value}`} style={{ width: `${(p.value / Math.max(total, 1)) * 100}%`, background: p.color }} />
        ) : null,
      )}
    </div>
  );
}

function Legend({ items }: { items: { color: string; text: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-[var(--viz-muted)]">
      {items.map((i) => (
        <span key={i.text} className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ background: i.color }} />
          {i.text}
        </span>
      ))}
    </div>
  );
}

/** The dashboard's headline numbers in one strip instead of a wall of tiles. */
export function OverviewStrip({ o }: { o: Overview }) {
  const t = useT();
  const openCases = o.cases.emergency + o.cases.high + o.cases.low;
  const sev = [
    { key: "emergency", value: o.cases.emergency, color: "var(--viz-critical)" },
    { key: "high", value: o.cases.high, color: "var(--viz-serious)" },
    { key: "low", value: o.cases.low, color: "var(--viz-warning)" },
  ];
  return (
    <section
      aria-label={t("dash.overview")}
      data-testid="overview"
      className="grid divide-y divide-[var(--viz-grid)] rounded-lg bg-[var(--viz-surface)] md:grid-cols-2 md:divide-y-0 xl:grid-cols-4 xl:divide-x"
    >
      <div className="p-5">
        <Label>{t("dash.convToday")}</Label>
        <div className="flex items-end justify-between gap-4">
          <div className="shrink-0">
            <Big>{o.today}</Big>
            <div className="text-xs text-[var(--viz-muted)]">{t("dash.thisMonth", { n: o.month })}</div>
          </div>
          <DailyColumns daily={o.daily} />
        </div>
      </div>

      <div className="p-5">
        <Label>{t("dash.firstResponse")}</Label>
        <div className="mt-1 grid grid-cols-2 gap-4">
          <div title={t("dash.replies", { n: o.botSamples })}>
            <Big>{duration(o.botMedian)}</Big>
            <div className="text-xs text-[var(--viz-muted)]">{t("thread.bot")}</div>
          </div>
          <div title={t("dash.replies", { n: o.staffSamples })}>
            <Big>{duration(o.staffMedian)}</Big>
            <div className="text-xs text-[var(--viz-muted)]">{t("thread.staff")}</div>
          </div>
        </div>
      </div>

      <div className="p-5">
        <Label>{t("dash.contacts")}</Label>
        <Big>{o.contacts.total}</Big>
        <div className="mt-2" />
        <SplitBar
          total={o.contacts.total}
          parts={[
            { value: o.contacts.subscribed, color: "var(--viz-seq)", label: t("contact.subscribed") },
            { value: o.contacts.opted_out, color: "var(--viz-critical)", label: "STOP" },
          ]}
        />
        <div className="mt-1.5" />
        <Legend
          items={[
            { color: "var(--viz-seq)", text: t("dash.subscribedN", { n: o.contacts.subscribed }) },
            { color: "var(--viz-critical)", text: `${o.contacts.opted_out} STOP` },
          ]}
        />
      </div>

      <Link href="/cases" className="block p-5 transition-colors hover:bg-[var(--viz-track)]/40" data-testid="overview-cases">
        <Label>{t("dash.openCases")}</Label>
        <Big>{openCases}</Big>
        <div className="mt-2" />
        <SplitBar total={openCases} parts={sev.map((s) => ({ value: s.value, color: s.color, label: t(`sev.${s.key}`) }))} />
        <div className="mt-1.5" />
        <Legend items={sev.map((s) => ({ color: s.color, text: `${s.value} ${t(`sev.${s.key}`).toLowerCase()}` }))} />
      </Link>
    </section>
  );
}
