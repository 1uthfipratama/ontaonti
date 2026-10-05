"use client";

import useSWR from "swr";
import { Download } from "lucide-react";

import { STAGES } from "@/components/journey-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_URL } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useStaff } from "@/lib/session";

type Programme = {
  days: number;
  stages: Record<string, number>;
  adherence: { taken: number; missed: number; skipped: number };
  screenings: { total: number; presumptive: number };
  reminders_on: number;
  flags_weekly: { week: string; low: number; high: number; emergency: number }[];
};

const SEV = [
  ["emergency", "var(--viz-critical)"],
  ["high", "var(--viz-serious)"],
  ["low", "var(--viz-warning)"],
] as const;

/** Risk flags per week: stacked columns, newest on the right. */
function WeeklyFlags({ weeks }: { weeks: Programme["flags_weekly"] }) {
  const t = useT();
  const max = Math.max(1, ...weeks.map((w) => w.low + w.high + w.emergency));
  return (
    <figure>
      <figcaption className="mb-2 text-xs text-[var(--viz-ink-2)]">{t("dash.flagsWeek")}</figcaption>
      <div className="flex h-24 items-end gap-1.5 border-b border-[var(--viz-grid)]">
        {weeks.map((w) => {
          const total = w.low + w.high + w.emergency;
          return (
            <div
              key={w.week}
              className="flex flex-1 flex-col-reverse overflow-hidden rounded-t"
              style={{ height: `${(total / max) * 100}%` }}
              title={`${w.week}: ${SEV.map(([k]) => `${t(`sev.${k}`)} ${w[k]}`).join(", ")}`}
            >
              {SEV.slice()
                .reverse()
                .map(([k, color]) => (
                  <div key={k} style={{ height: total ? `${(w[k] / total) * 100}%` : 0, background: color }} />
                ))}
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-3 text-[11px] text-[var(--viz-ink-2)]">
        {SEV.map(([k, color]) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span className="size-2 rounded-full" style={{ background: color }} />
            {t(`sev.${k}`)}
          </span>
        ))}
      </div>
    </figure>
  );
}

function Figure({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-xs text-[var(--viz-ink-2)]">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-[var(--viz-ink)]">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-[var(--viz-muted)]">{sub}</div>}
    </div>
  );
}

export function ProgrammeCard() {
  const t = useT();
  const role = useStaff().role;
  const { data } = useSWR<Programme>("/reports/programme", { refreshInterval: 60000 });
  if (!data) return null;
  const asked = data.adherence.taken + data.adherence.missed;
  const pct = asked ? `${Math.round((data.adherence.taken / asked) * 100)}%` : "—";
  return (
    <Card data-testid="programme-card">
      <CardHeader className="flex flex-row items-center gap-3">
        <CardTitle className="flex-1 text-sm">{t("dash.programme")}</CardTitle>
        {role !== "agent" && (
          <div className="flex items-center gap-3 text-xs">
            <Download className="size-3.5 text-muted-foreground" />
            <span className="text-muted-foreground">{t("dash.export")}:</span>
            {(["patients", "doses", "screenings", "cases"] as const).map((k) => (
              <a key={k} href={`${API_URL}/reports/export/${k}.csv`} className="font-medium text-primary hover:underline">
                {t(`dash.csv.${k}`)}
              </a>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent className="grid gap-8 lg:grid-cols-[1fr_1fr_1.4fr]">
        <div className="space-y-5">
          <Figure label={t("dash.adherence")} value={pct} sub={t("dash.adherenceSub", { taken: data.adherence.taken, total: asked })} />
          <Figure
            label={t("dash.screenings")}
            value={String(data.screenings.total)}
            sub={t("dash.screeningsSub", { n: data.screenings.presumptive })}
          />
        </div>
        <div>
          <div className="mb-2 text-xs text-[var(--viz-ink-2)]">{t("dash.journey")}</div>
          <dl className="space-y-1.5 text-sm">
            {STAGES.map((s) => (
              <div key={s} className="flex justify-between gap-3">
                <dt className="text-[var(--viz-ink-2)]">{t(`stage.${s}`)}</dt>
                <dd className="font-medium tabular-nums text-[var(--viz-ink)]">{data.stages[s] ?? 0}</dd>
              </div>
            ))}
          </dl>
        </div>
        <WeeklyFlags weeks={data.flags_weekly} />
      </CardContent>
    </Card>
  );
}
