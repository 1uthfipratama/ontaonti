"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Search } from "lucide-react";

import { channelName } from "@/components/badges";
import { MessageBubble } from "@/components/message-bubble";
import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { clock, timeAgo } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useCanAct } from "@/lib/session";
import type { Channel, Contact, Conversation, Message } from "@/lib/types";
import { cn } from "@/lib/utils";

type ContactRow = Contact & { last_message_at: string | null };
type ContactDetail = Contact & {
  consents: { kind: string; status: string; source: string; channel: string | null; created_at: string }[];
  conversations: Conversation[];
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function Detail({ id, all }: { id: number; all: ContactRow[] }) {
  const t = useT();
  const { mutate } = useSWRConfig();
  const router = useRouter();
  const canAct = useCanAct();
  const { data: c } = useSWR<ContactDetail>(`/contacts/${id}`);
  const { data: timeline } = useSWR<(Message & { channel: Channel })[]>(`/contacts/${id}/timeline`);
  const [mergeId, setMergeId] = useState("");
  const [notes, setNotes] = useState<string | null>(null);
  const refresh = () => mutate((k) => typeof k === "string" && k.startsWith("/contacts"));

  async function run(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      toast.success(ok);
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  if (!c) return <div className="bg-card p-6 text-sm text-muted-foreground">{t("common.loading")}</div>;
  const others = all.filter((o) => o.id !== id);
  let lastChannel = "";
  return (
    <div className="grid h-full grid-rows-[minmax(0,1fr)] grid-cols-[minmax(0,1fr)] overflow-hidden xl:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="flex min-h-0 flex-col bg-card">
        <div className="border-b border-border px-6 py-3">
          <h2 className="text-[15px] font-semibold">{c.display_name}</h2>
          <p className="text-xs text-muted-foreground">{t("contacts.timeline")}</p>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4" data-testid="timeline">
          {timeline?.map((m) => {
            const showChannel = m.channel !== lastChannel;
            lastChannel = m.channel;
            return (
              <div key={m.id}>
                {showChannel && (
                  <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="h-px flex-1 bg-border" />
                    {channelName(m.channel)}
                    <span className="h-px flex-1 bg-border" />
                  </div>
                )}
                <MessageBubble m={m} />
              </div>
            );
          })}
        </div>
      </div>

      <div className="hidden space-y-6 overflow-y-auto border-l border-border bg-card p-5 text-sm xl:block">
        <Section title={t("contact.channels")}>
          {c.identities.map((i) => (
            <div key={i.id} className="flex justify-between gap-2">
              <span className="text-muted-foreground">{channelName(i.channel)}</span>
              <span className="truncate font-mono text-xs">{i.simulated ? t("common.simulated") : i.external_id}</span>
            </div>
          ))}
          {c.conversations.map((v) => (
            <Link key={v.id} href={`/inbox?c=${v.id}`} className="block text-xs text-primary hover:underline">
              {t("contacts.openConversation", { channel: channelName(v.channel) })} · {timeAgo(v.last_message_at, t)}
            </Link>
          ))}
        </Section>

        <Section title={t("contacts.consent")}>
          <div className="flex justify-between">
            <span className="text-muted-foreground">{t("contact.messages")}</span>
            {c.opted_out ? <span className="text-destructive">{t("contact.optedOut")}</span> : <span>{t("contact.active")}</span>}
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-muted-foreground">{t("contact.broadcasts")}</span>
            <span>{c.broadcast_opt_in ? t("contact.subscribed") : t("contact.notSubscribed")}</span>
          </div>
          {canAct && (
            <Button
              size="xs"
              variant="ghost"
              className="-ml-2 text-primary"
              onClick={() =>
                run(() => api(`/contacts/${id}/consent`, { json: { broadcast: !c.broadcast_opt_in } }), t("contacts.consentRecorded"))
              }
            >
              {c.broadcast_opt_in ? t("contacts.revokeConsent") : t("contacts.recordConsent")}
            </Button>
          )}
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {c.consents.map((k, i) => (
              <li key={i}>
                {clock(k.created_at)} · {k.kind} {k.status} ({k.source})
              </li>
            ))}
          </ul>
        </Section>

        <Section title={t("contact.notes")}>
          <Textarea
            value={notes ?? c.notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={!canAct}
            placeholder={t("contacts.notesPlaceholder")}
            className="min-h-20"
          />
          {canAct && notes !== null && notes !== c.notes && (
            <Button
              size="sm"
              onClick={() =>
                run(async () => {
                  await api(`/contacts/${id}`, { method: "PATCH", json: { notes } });
                  setNotes(null);
                }, t("common.saved"))
              }
            >
              {t("contacts.saveNotes")}
            </Button>
          )}
        </Section>

        {canAct && others.length > 0 && (
          <Section title={t("contacts.merge")}>
            <NativeSelect
              data-testid="merge-select"
              className="w-full"
              value={mergeId}
              onChange={(e) => setMergeId(e.target.value)}
              options={[
                { value: "", label: t("contacts.chooseContact") },
                ...others.map((o) => ({
                  value: String(o.id),
                  label: `${o.display_name} (${o.identities.map((i) => channelName(i.channel)).join(", ")})`,
                })),
              ]}
            />
            <Button
              size="sm"
              variant="outline"
              disabled={!mergeId}
              onClick={() =>
                run(async () => {
                  await api(`/contacts/${id}/merge`, { json: { source_contact_id: Number(mergeId) } });
                  setMergeId("");
                  router.replace(`/contacts?id=${id}`);
                }, t("contacts.merged"))
              }
            >
              {t("contacts.mergeButton")}
            </Button>
            <p className="text-xs text-muted-foreground">
              {t("contacts.mergeHint")}
            </p>
          </Section>
        )}
      </div>
    </div>
  );
}

function Contacts() {
  const params = useSearchParams();
  const router = useRouter();
  const t = useT();
  const selected = params.get("id") ? Number(params.get("id")) : null;
  const [q, setQ] = useState("");
  const { data } = useSWR<ContactRow[]>(`/contacts${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  return (
    <div className="grid h-full grid-rows-[minmax(0,1fr)] grid-cols-[17rem_minmax(0,1fr)] xl:grid-cols-[21rem_minmax(0,1fr)]">
      <div className="flex flex-col border-r border-border bg-card">
        <div className="relative p-3">
          <Search className="pointer-events-none absolute top-5.5 left-6 size-4 text-muted-foreground" />
          <Input placeholder={t("contacts.search")} value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {data?.map((c) => (
            <button
              key={c.id}
              onClick={() => router.push(`/contacts?id=${c.id}`)}
              className={cn(
                "block w-full rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted",
                selected === c.id && "bg-accent hover:bg-accent",
              )}
            >
              <div className="flex items-center gap-2">
                <span className="flex-1 truncate text-sm font-medium">{c.display_name}</span>
                <span className="text-xs text-muted-foreground">{timeAgo(c.last_message_at, t)}</span>
              </div>
              <div className="mt-0.5 truncate text-xs text-muted-foreground">
                {[
                  c.identities.map((i) => channelName(i.channel)).join(", "),
                  c.broadcast_opt_in ? t("contacts.subscribed") : "",
                  c.opted_out ? t("contacts.optedOut") : "",
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </button>
          ))}
        </div>
      </div>
      {selected ? (
        <Detail key={selected} id={selected} all={data ?? []} />
      ) : (
        <div className="flex items-center justify-center bg-card text-sm text-muted-foreground">{t("contacts.select")}</div>
      )}
    </div>
  );
}

export default function ContactsPage() {
  return (
    <Suspense>
      <Contacts />
    </Suspense>
  );
}
