"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { BellRing, ListChecks } from "lucide-react";

import { STAGES, treatmentMonth } from "@/components/journey-panel";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useCanAct } from "@/lib/session";
import type { Contact, Stage } from "@/lib/types";
import { cn } from "@/lib/utils";

type Card = Contact & { kader_name: string | null; week: Record<string, number>; open_tasks: number };
type Board = { stages: Stage[]; contacts: Card[] };

function PatientCard({ c, draggable }: { c: Card; draggable: boolean }) {
  const t = useT();
  const month = c.journey_stage === "treatment" ? treatmentMonth(c.treatment_start) : null;
  const taken = c.week.taken ?? 0;
  const asked = taken + (c.week.missed ?? 0);
  const meta = [c.puskesmas, c.kader_name].filter(Boolean).join(" · ");
  return (
    <Link
      href={`/contacts?id=${c.id}`}
      draggable={draggable}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(c.id))}
      data-testid="patient-card"
      className="block rounded-md bg-card px-3 py-2.5 shadow-[0_1px_2px_rgba(39,43,50,0.06)] hover:ring-1 hover:ring-border"
    >
      <div className="flex items-center gap-2">
        <span className="flex-1 truncate text-sm font-medium">{c.display_name}</span>
        {month && <span className="shrink-0 text-xs text-muted-foreground">{t("board.month", { n: month })}</span>}
      </div>
      {meta && <div className="mt-0.5 truncate text-xs text-muted-foreground">{meta}</div>}
      {(asked > 0 || c.open_tasks > 0 || c.reminder_enabled) && (
        <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
          {c.reminder_enabled && <BellRing className="size-3.5" aria-label={t("journey.reminder")} />}
          {asked > 0 && (
            <span className={cn(taken < asked && "font-medium text-destructive")}>
              {t("board.week", { taken, total: asked })}
            </span>
          )}
          {c.open_tasks > 0 && (
            <span className="inline-flex items-center gap-1">
              <ListChecks className="size-3.5" />
              {c.open_tasks}
            </span>
          )}
        </div>
      )}
    </Link>
  );
}

export default function PatientsPage() {
  const t = useT();
  const canAct = useCanAct();
  const { mutate } = useSWRConfig();
  const { data } = useSWR<Board>("/journey");
  const [over, setOver] = useState<Stage | null>(null);

  async function move(contactId: number, stage: Stage) {
    const card = data?.contacts.find((c) => c.id === contactId);
    if (!card || card.journey_stage === stage) return;
    // Optimistic: move the card now, then confirm with the server.
    mutate("/journey", { ...data!, contacts: data!.contacts.map((c) => (c.id === contactId ? { ...c, journey_stage: stage } : c)) }, { revalidate: false });
    try {
      await api(`/contacts/${contactId}/journey`, { method: "PATCH", json: { stage } });
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
    mutate((k) => typeof k === "string" && (k.startsWith("/journey") || k.startsWith("/contacts")));
  }

  if (!data) return <div className="p-6 text-sm text-muted-foreground">{t("common.loading")}</div>;
  return (
    <div className="flex h-full flex-col">
      {data.contacts.length === 0 && <p className="px-6 pt-5 text-sm text-muted-foreground">{t("board.empty")}</p>}
      <div className="grid min-h-0 flex-1 auto-cols-[minmax(12.5rem,1fr)] grid-flow-col gap-3 overflow-x-auto p-4">
        {STAGES.map((stage) => {
          const cards = data.contacts.filter((c) => c.journey_stage === stage);
          return (
            <div
              key={stage}
              data-testid={`stage-${stage}`}
              onDragOver={(e) => {
                if (!canAct) return;
                e.preventDefault();
                setOver(stage);
              }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => {
                e.preventDefault();
                setOver(null);
                move(Number(e.dataTransfer.getData("text/plain")), stage);
              }}
              className={cn("flex min-h-0 flex-col rounded-lg bg-secondary/60 transition-colors", over === stage && "bg-accent")}
            >
              <div className="flex items-center gap-2 px-3 pt-3 pb-2 text-sm font-semibold">
                {t(`stage.${stage}`)}
                <span className="text-xs font-normal text-muted-foreground">{cards.length}</span>
              </div>
              <div className="flex-1 space-y-2 overflow-y-auto px-2 pb-2">
                {cards.map((c) => (
                  <PatientCard key={c.id} c={c} draggable={canAct} />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
