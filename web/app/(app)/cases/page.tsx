"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { channelName, SeverityBadge, SeverityDot, useCategory } from "@/components/badges";
import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { clock, timeAgo } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useCanAct } from "@/lib/session";
import type { Case } from "@/lib/types";
import { cn } from "@/lib/utils";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm">{children}</div>
    </div>
  );
}

function CaseDetail({ id }: { id: number }) {
  const t = useT();
  const { mutate } = useSWRConfig();
  const canAct = useCanAct();
  const { data: c } = useSWR<Case>(`/cases/${id}`);
  const [note, setNote] = useState("");
  const refresh = () =>
    mutate((k) => typeof k === "string" && (k.startsWith("/cases") || k.startsWith("/notifications")));

  async function act(path: string, json?: unknown) {
    try {
      await api(`/cases/${id}${path}`, { method: "POST", json });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  if (!c) return <div className="bg-card p-6 text-sm text-muted-foreground">{t("common.loading")}</div>;
  return (
    <div className="h-full overflow-y-auto bg-card">
      <div className="flex items-start gap-4 border-b border-border px-6 py-4">
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h2 className="text-[15px] font-semibold">{t("cases.title", { id: c.id })}</h2>
            <SeverityBadge severity={c.severity} category={c.category} />
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {t(`cases.status.${c.status}`)} · {t("cases.opened", { date: clock(c.created_at) })}
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Link href={`/inbox?c=${c.conversation_id}`}>
            <Button size="sm" variant="ghost">{t("cases.openConversation")}</Button>
          </Link>
          {canAct && c.status === "OPEN" && (
            <Button size="sm" variant="outline" onClick={() => act("/claim")} data-testid="claim-case">
              {t("cases.claim")}
            </Button>
          )}
          {canAct && c.status === "CLAIMED" && (
            <Button size="sm" variant="ghost" onClick={() => act("/status", { status: "OPEN" })}>
              {t("cases.unclaim")}
            </Button>
          )}
          {canAct && c.status !== "RESOLVED" && (
            <>
              <Button size="sm" variant="outline" onClick={() => act("/resolve", { return_to_bot: false })}>
                {t("cases.resolveKeep")}
              </Button>
              <Button size="sm" onClick={() => act("/resolve", { return_to_bot: true })} data-testid="resolve-case">
                {t("cases.resolveBot")}
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="space-y-8 px-6 py-5">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 lg:grid-cols-4">
          <Field label={t("cases.contact")}>{c.contact_name}</Field>
          <Field label={t("cases.channel")}>{channelName(c.channel)}</Field>
          <Field label={t("cases.assigned")}>{c.assigned_name ?? t("cases.nobody")}</Field>
          <Field label={t("cases.mode")}>{c.conversation_mode === "HUMAN" ? t("inbox.staffHandling") : t("inbox.bot")}</Field>
        </div>

        {c.trigger_text && (
          <section>
            <h3 className="mb-2 text-xs font-semibold text-muted-foreground">{t("cases.trigger")}</h3>
            <p className="rounded-lg bg-secondary px-4 py-3 text-sm">{c.trigger_text}</p>
            <p className="mt-1.5 text-xs text-muted-foreground whitespace-pre-wrap">{c.reason}</p>
          </section>
        )}

        <section>
          <h3 className="mb-2 text-xs font-semibold text-muted-foreground">{t("cases.notes")}</h3>
          {c.notes?.length === 0 && <p className="text-sm text-muted-foreground">{t("cases.noNotes")}</p>}
          <ul className="space-y-3">
            {c.notes?.map((n) => (
              <li key={n.id}>
                <div className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{n.author}</span> · {clock(n.created_at)}
                </div>
                <p className="mt-0.5 whitespace-pre-wrap text-sm">{n.text}</p>
              </li>
            ))}
          </ul>
          {canAct && (
            <div className="mt-4 flex items-end gap-2">
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("cases.notePlaceholder")} className="min-h-10" />
              <Button
                variant="outline"
                disabled={!note.trim()}
                onClick={async () => {
                  await act("/notes", { text: note });
                  setNote("");
                }}
              >
                {t("cases.addNote")}
              </Button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Cases() {
  const params = useSearchParams();
  const router = useRouter();
  const t = useT();
  const category = useCategory();
  const selected = params.get("id") ? Number(params.get("id")) : null;
  const [status, setStatus] = useState("active");
  const { data } = useSWR<Case[]>(`/cases?status=${status}`);
  return (
    <div className="grid h-full grid-rows-[minmax(0,1fr)] grid-cols-[17rem_minmax(0,1fr)] xl:grid-cols-[22rem_minmax(0,1fr)]">
      <div className="flex flex-col border-r border-border bg-card">
        <div className="p-3">
          <NativeSelect
            aria-label={t("inbox.filterStatus")}
            className="w-full"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            options={[
              { value: "active", label: t("cases.filterActive") },
              { value: "OPEN", label: t("cases.filterOpen") },
              { value: "CLAIMED", label: t("cases.filterClaimed") },
              { value: "RESOLVED", label: t("cases.filterResolved") },
              { value: "all", label: t("cases.filterAll") },
            ]}
          />
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2" data-testid="case-list">
          {data?.length === 0 && <p className="p-3 text-sm text-muted-foreground">{t("cases.empty")}</p>}
          {data?.map((c) => (
            <button
              key={c.id}
              onClick={() => router.push(`/cases?id=${c.id}`)}
              className={cn(
                "block w-full rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted",
                selected === c.id && "bg-accent hover:bg-accent",
              )}
            >
              <div className="flex items-center gap-2">
                <SeverityDot severity={c.severity} />
                <span className="flex-1 truncate text-sm font-medium">{c.contact_name}</span>
                <span className="text-xs text-muted-foreground">{timeAgo(c.created_at, t)}</span>
              </div>
              <div className="mt-0.5 truncate text-[13px] text-muted-foreground">{c.trigger_text}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                {[t(`sev.${c.severity}`), category(c.category, c.severity), t(`cases.status.${c.status}`)]
                  .filter(Boolean)
                  .join(" · ")}
                {c.assigned_name ? ` · ${c.assigned_name}` : ""}
              </div>
            </button>
          ))}
        </div>
      </div>
      {selected ? (
        <CaseDetail key={selected} id={selected} />
      ) : (
        <div className="flex items-center justify-center bg-card text-sm text-muted-foreground">{t("cases.select")}</div>
      )}
    </div>
  );
}

export default function CasesPage() {
  return (
    <Suspense>
      <Cases />
    </Suspense>
  );
}
