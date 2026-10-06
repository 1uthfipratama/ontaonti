"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Check, Home, MoreHorizontal, Phone } from "lucide-react";

import { DateField } from "@/components/date-time-field";
import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useCanAct, useStaff } from "@/lib/session";
import type { Staff, Task } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICON = { call: Phone, visit: Home, other: MoreHorizontal };

function todayISO(): string {
  return new Date().toLocaleDateString("sv-SE");
}

function NewTask() {
  const t = useT();
  const me = useStaff();
  const { mutate } = useSWRConfig();
  const { data: staff } = useSWR<Staff[]>("/staff");
  const [form, setForm] = useState({ title: "", kind: "call", due: todayISO(), assigned_to: String(me.id) });

  async function add() {
    try {
      await api("/tasks", {
        json: { ...form, assigned_to: form.assigned_to ? Number(form.assigned_to) : null, due: form.due || null },
      });
      setForm({ ...form, title: "" });
      mutate((k) => typeof k === "string" && (k.startsWith("/tasks") || k.startsWith("/notifications")));
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <form
      className="flex flex-wrap items-center gap-2 rounded-lg bg-card p-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (form.title.trim()) add();
      }}
    >
      <Input
        value={form.title}
        onChange={(e) => setForm({ ...form, title: e.target.value })}
        placeholder={t("tasks.titlePlaceholder")}
        className="min-w-56 flex-1"
        data-testid="task-title"
      />
      <NativeSelect
        aria-label={t("tasks.kind.call")}
        value={form.kind}
        onChange={(e) => setForm({ ...form, kind: e.target.value })}
        options={(["call", "visit", "other"] as const).map((k) => ({ value: k, label: t(`tasks.kind.${k}`) }))}
      />
      <DateField aria-label={t("tasks.due")} className="w-40" placeholder={t("tasks.noDate")} value={form.due} onChange={(v) => setForm({ ...form, due: v })} />
      <NativeSelect
        aria-label={t("tasks.assignee")}
        value={form.assigned_to}
        onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
        options={[
          { value: "", label: t("tasks.unassigned") },
          ...(staff ?? []).filter((s) => s.is_active).map((s) => ({ value: String(s.id), label: s.name || s.email })),
        ]}
      />
      <Button type="submit" disabled={!form.title.trim()}>
        {t("tasks.add")}
      </Button>
    </form>
  );
}

function TaskRow({ task }: { task: Task }) {
  const t = useT();
  const canAct = useCanAct();
  const { mutate } = useSWRConfig();
  const [closing, setClosing] = useState(false);
  const [outcome, setOutcome] = useState("");
  const Icon = ICON[task.kind];
  const overdue = task.status === "open" && task.due !== null && task.due < todayISO();

  async function patch(json: Record<string, unknown>) {
    try {
      await api(`/tasks/${task.id}`, { method: "PATCH", json });
      mutate((k) => typeof k === "string" && (k.startsWith("/tasks") || k.startsWith("/notifications") || k.startsWith("/journey")));
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <div className="px-5 py-3" data-testid="task-row">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label={t(`tasks.kind.${task.kind}`)} />
        <div className="min-w-0 flex-1">
          <div className={cn("text-sm", task.status === "done" && "text-muted-foreground line-through")}>{task.title}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {[
              task.due && <span key="d" className={cn(overdue && "font-medium text-destructive")}>{task.due}</span>,
              task.contact_id && (
                <Link key="c" href={`/contacts?id=${task.contact_id}`} className="text-primary hover:underline">
                  {task.contact_name}
                </Link>
              ),
              <span key="a">{task.assigned_name ?? t("tasks.unassigned")}</span>,
              task.source !== "staff" && <span key="s">{t("tasks.auto")}</span>,
            ]
              .filter(Boolean)
              .flatMap((el, i) => (i ? [" · ", el] : [el]))}
          </div>
          {task.outcome && <p className="mt-1 text-sm text-muted-foreground">{task.outcome}</p>}
        </div>
        {canAct && task.status === "open" && !closing && (
          <Button size="sm" variant="outline" onClick={() => setClosing(true)} data-testid="task-done">
            <Check /> {t("tasks.complete")}
          </Button>
        )}
        {canAct && task.status === "done" && (
          <Button size="sm" variant="ghost" onClick={() => patch({ status: "open" })}>
            {t("tasks.reopen")}
          </Button>
        )}
      </div>
      {closing && (
        <form
          className="mt-2 flex gap-2 pl-7"
          onSubmit={(e) => {
            e.preventDefault();
            patch({ status: "done", outcome });
          }}
        >
          <Input autoFocus value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder={t("tasks.outcome")} data-testid="task-outcome" />
          <Button type="submit">{t("tasks.complete")}</Button>
        </form>
      )}
    </div>
  );
}

function Tasks() {
  const t = useT();
  const router = useRouter();
  const canAct = useCanAct();
  const view = useSearchParams().get("view") ?? "mine";
  const key = view === "done" ? "/tasks?status=done" : view === "all" ? "/tasks" : "/tasks?scope=mine";
  const { data } = useSWR<Task[]>(key);
  const today = todayISO();
  const groups =
    view === "done"
      ? [{ label: "", items: data ?? [] }]
      : [
          { label: t("tasks.overdue"), items: (data ?? []).filter((x) => x.due && x.due < today) },
          { label: t("tasks.today"), items: (data ?? []).filter((x) => x.due === today) },
          { label: t("tasks.upcoming"), items: (data ?? []).filter((x) => x.due && x.due > today) },
          { label: t("tasks.noDate"), items: (data ?? []).filter((x) => !x.due) },
        ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <div className="flex gap-1 border-b border-border">
          {(["mine", "all", "done"] as const).map((v) => (
            <button
              key={v}
              onClick={() => router.replace(`/tasks?view=${v}`)}
              className={cn(
                "-mb-px border-b-2 px-3 py-2 text-sm",
                view === v ? "border-primary font-semibold" : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t(`tasks.${v}`)}
            </button>
          ))}
        </div>
        {canAct && view !== "done" && <NewTask />}
        {data?.length === 0 && <p className="text-sm text-muted-foreground">{t("tasks.empty")}</p>}
        {groups
          .filter((g) => g.items.length)
          .map((g) => (
            <section key={g.label}>
              {g.label && <h2 className="mb-2 text-xs font-semibold text-muted-foreground">{g.label}</h2>}
              <div className="divide-y divide-divider rounded-lg bg-card">
                {g.items.map((task) => (
                  <TaskRow key={task.id} task={task} />
                ))}
              </div>
            </section>
          ))}
      </div>
    </div>
  );
}

export default function TasksPage() {
  return (
    <Suspense>
      <Tasks />
    </Suspense>
  );
}
