"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { DateField, TimeField } from "@/components/date-time-field";
import { NativeSelect } from "@/components/native-select";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { api, errorMessage } from "@/lib/api";
import { day } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useCanAct } from "@/lib/session";
import type { Contact, DoseDay, Stage, Staff, Task } from "@/lib/types";
import { cn } from "@/lib/utils";

export const STAGES: Stage[] = ["suspect", "testing", "treatment", "completed", "lost"];

/** Month n of treatment (1-based), or null. */
export function treatmentMonth(start: string | null): number | null {
  if (!start) return null;
  const s = new Date(start + "T00:00:00");
  const now = new Date();
  if (s > now) return null;
  let months = (now.getFullYear() - s.getFullYear()) * 12 + now.getMonth() - s.getMonth();
  if (now.getDate() < s.getDate()) months -= 1;
  return months + 1;
}

const DOT: Record<string, string> = {
  taken: "bg-[var(--success-foreground)]",
  missed: "bg-destructive",
  pending: "bg-[var(--sev-low)]",
};

/** Last 14 days as dots: taken / missed / no data. */
export function DoseDots({ contactId }: { contactId: number }) {
  const t = useT();
  const { data } = useSWR<DoseDay[]>(`/contacts/${contactId}/doses?days=14`);
  const byDay = new Map((data ?? []).map((d) => [d.day, d.status]));
  const days = Array.from({ length: 14 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - 13 + i);
    return d.toLocaleDateString("sv-SE"); // YYYY-MM-DD, local
  });
  const taken = days.filter((d) => byDay.get(d) === "taken").length;
  const missed = days.filter((d) => byDay.get(d) === "missed").length;
  return (
    <div>
      <div className="flex gap-1" data-testid="dose-dots">
        {days.map((d) => {
          const st = byDay.get(d);
          return (
            <span
              key={d}
              title={`${d}: ${st === "taken" ? t("journey.taken") : st === "missed" ? t("journey.missed") : t("journey.noReply")}`}
              className={cn("size-2.5 rounded-full", (st && DOT[st]) || "bg-border")}
            />
          );
        })}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        {t("journey.taken")} {taken} · {t("journey.missed")} {missed}
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="shrink-0 whitespace-nowrap text-muted-foreground">{label}</span>
      <div className="flex min-w-0 items-center justify-end">{children}</div>
    </div>
  );
}

function LatestScreening({ contactId }: { contactId: number }) {
  const t = useT();
  const { data } = useSWR<{ result: string; finished_at: string } | null>(`/contacts/${contactId}/screening`);
  if (!data) return null;
  return (
    <Row label={t("journey.screening")}>
      <span className={cn("text-sm", data.result === "presumptive" && "font-medium text-destructive")} data-testid="screening-result">
        {data.result === "presumptive" ? t("journey.screenPositive") : t("journey.screenNegative")}
        <span className="font-normal text-muted-foreground"> · {day(data.finished_at)}</span>
      </span>
    </Row>
  );
}

/** Treatment details, reminder and open tasks, for the contact side panels. */
export function JourneyPanel({ contact: c }: { contact: Contact }) {
  const t = useT();
  const canAct = useCanAct();
  const { mutate } = useSWRConfig();
  const { data: staff } = useSWR<Staff[]>("/staff");
  const { data: tasks } = useSWR<Task[]>(`/tasks?contact_id=${c.id}`);
  const [puskesmas, setPuskesmas] = useState<string | null>(null);
  const [newTask, setNewTask] = useState("");
  const onTreatment = c.journey_stage === "treatment";
  const month = treatmentMonth(c.treatment_start);

  async function save(json: Record<string, unknown>) {
    try {
      await api(`/contacts/${c.id}/journey`, { method: "PATCH", json });
      mutate((k) => typeof k === "string" && (k.startsWith("/conversations") || k.startsWith("/contacts") || k.startsWith("/journey")));
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  async function addTask() {
    try {
      await api("/tasks", { json: { contact_id: c.id, title: newTask, kind: "call", assigned_to: c.kader_id } });
      setNewTask("");
      mutate((k) => typeof k === "string" && k.startsWith("/tasks"));
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <section className="space-y-2.5" data-testid="journey-panel">
      <h3 className="text-xs font-semibold text-muted-foreground">{t("journey.title")}</h3>
      <Row label={t("journey.stage")}>
        <NativeSelect
          aria-label={t("journey.stage")}
          data-testid="journey-stage"
          disabled={!canAct}
          className="h-8 max-w-40 text-sm"
          value={c.journey_stage ?? ""}
          onChange={(e) => save(e.target.value ? { stage: e.target.value } : { clear_stage: true })}
          options={[{ value: "", label: t("stage.none") }, ...STAGES.map((s) => ({ value: s, label: t(`stage.${s}`) }))]}
        />
      </Row>
      <LatestScreening contactId={c.id} />
      {c.journey_stage && (
        <>
          {onTreatment && (
            <Row label={t("journey.start")}>
              <DateField
                aria-label={t("journey.start")}
                disabled={!canAct}
                className="h-8 w-40"
                value={c.treatment_start ?? ""}
                onChange={(v) => v && save({ treatment_start: v })}
              />
            </Row>
          )}
          {onTreatment && month && (
            <p className="text-right text-xs text-muted-foreground">
              {t("journey.month", { n: month, total: c.treatment_months })}
            </p>
          )}
          <Row label={t("journey.puskesmas")}>
            <Input
              disabled={!canAct}
              className="h-8 w-40"
              value={puskesmas ?? c.puskesmas}
              onChange={(e) => setPuskesmas(e.target.value)}
              onBlur={() => {
                if (puskesmas !== null && puskesmas !== c.puskesmas) save({ puskesmas });
                setPuskesmas(null);
              }}
            />
          </Row>
          <Row label={t("journey.kader")}>
            <NativeSelect
              aria-label={t("journey.kader")}
              disabled={!canAct}
              className="h-8 max-w-40 text-sm"
              value={c.kader_id ? String(c.kader_id) : ""}
              onChange={(e) => save(e.target.value ? { kader_id: Number(e.target.value) } : { clear_kader: true })}
              options={[
                { value: "", label: t("journey.none") },
                ...(staff ?? []).filter((s) => s.is_active).map((s) => ({ value: String(s.id), label: s.name || s.email })),
              ]}
            />
          </Row>
          {onTreatment && (
            <>
              <Row label={t("journey.reminder")}>
                {c.reminder_enabled && (
                  <TimeField
                    aria-label={t("journey.reminder")}
                    disabled={!canAct}
                    className="mr-2 h-8 w-24"
                    value={c.reminder_time}
                    onChange={(v) => save({ reminder_time: v })}
                  />
                )}
                <Switch
                  data-testid="reminder-switch"
                  checked={c.reminder_enabled}
                  disabled={!canAct || c.opted_out}
                  onCheckedChange={(v) => save({ reminder_enabled: v })}
                />
              </Row>
              <div className="pt-1">
                <div className="mb-1.5 text-xs text-muted-foreground">{t("journey.last14")}</div>
                <DoseDots contactId={c.id} />
              </div>
            </>
          )}
        </>
      )}

      {(c.journey_stage || (tasks?.length ?? 0) > 0) && (
        <div className="space-y-1.5 pt-2">
          <div className="text-xs font-semibold text-muted-foreground">{t("journey.tasks")}</div>
          {tasks?.map((task) => (
            <Link key={task.id} href="/tasks" className="block truncate text-sm hover:text-primary">
              {task.title}
              {task.due && <span className="text-xs text-muted-foreground"> · {task.due}</span>}
            </Link>
          ))}
          {canAct && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (newTask.trim()) addTask();
              }}
            >
              <Input
                value={newTask}
                onChange={(e) => setNewTask(e.target.value)}
                placeholder={`+ ${t("tasks.new")}`}
                className="h-8"
                data-testid="quick-task"
              />
            </form>
          )}
        </div>
      )}
    </section>
  );
}
