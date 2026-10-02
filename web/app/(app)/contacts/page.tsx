"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { ChannelBadge } from "@/components/badges";
import { MessageBubble } from "@/components/message-bubble";
import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { clock, timeAgo } from "@/lib/format";
import { useCanAct } from "@/lib/session";
import type { Channel, Contact, Conversation, Message } from "@/lib/types";
import { cn } from "@/lib/utils";

type ContactRow = Contact & { last_message_at: string | null };
type ContactDetail = Contact & {
  consents: { kind: string; status: string; source: string; channel: string | null; created_at: string }[];
  conversations: Conversation[];
};

function Detail({ id, all }: { id: number; all: ContactRow[] }) {
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
      toast.error(errorMessage(e));
    }
  }

  if (!c) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  const others = all.filter((o) => o.id !== id);
  return (
    <div className="grid h-full grid-cols-[1fr_20rem] overflow-hidden">
      <div className="flex min-h-0 flex-col">
        <div className="border-b px-4 py-3">
          <h2 className="font-semibold">{c.display_name}</h2>
          <p className="text-xs text-muted-foreground">Timeline across all channels</p>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3" data-testid="timeline">
          {timeline?.map((m) => (
            <div key={m.id}>
              {m.direction !== "note" && (
                <div className={cn("text-[10px]", m.direction === "in" ? "text-left" : "text-right")}>
                  <ChannelBadge channel={m.channel} />
                </div>
              )}
              <MessageBubble m={m} />
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-4 overflow-y-auto border-l p-4 text-sm">
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Identities</div>
          {c.identities.map((i) => (
            <div key={i.id} className="mb-1 flex items-center gap-2">
              <ChannelBadge channel={i.channel} simulated={i.simulated} />
              <span className="truncate font-mono text-xs">{i.external_id}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Conversations</div>
          {c.conversations.map((v) => (
            <Link key={v.id} href={`/inbox?c=${v.id}`} className="block text-xs text-primary hover:underline">
              #{v.id} {v.channel} · {v.mode} · {timeAgo(v.last_message_at)}
            </Link>
          ))}
        </div>
        <div className="space-y-1 text-xs">
          <div>Messaging: {c.opted_out ? <b className="text-red-600">opted out (STOP)</b> : "active"}</div>
          <div className="flex items-center gap-2">
            Broadcasts: {c.broadcast_opt_in ? "subscribed" : "not subscribed"}
            {canAct && (
              <Button
                size="xs"
                variant="outline"
                onClick={() =>
                  run(() => api(`/contacts/${id}/consent`, { json: { broadcast: !c.broadcast_opt_in } }), "Consent recorded")
                }
              >
                {c.broadcast_opt_in ? "Revoke" : "Record consent"}
              </Button>
            )}
          </div>
        </div>
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Consent log</div>
          <ul className="space-y-0.5 text-[11px]">
            {c.consents.map((k, i) => (
              <li key={i}>
                {clock(k.created_at)} · {k.kind} {k.status} ({k.source}
                {k.channel ? `, ${k.channel}` : ""})
              </li>
            ))}
            {c.consents.length === 0 && <li className="text-muted-foreground">Nothing yet.</li>}
          </ul>
        </div>
        <div>
          <div className="mb-1 text-xs uppercase text-muted-foreground">Notes</div>
          <Textarea
            value={notes ?? c.notes}
            onChange={(e) => setNotes(e.target.value)}
            disabled={!canAct}
            className="min-h-20 text-xs"
          />
          {canAct && notes !== null && notes !== c.notes && (
            <Button
              size="xs"
              className="mt-1"
              onClick={() =>
                run(async () => {
                  await api(`/contacts/${id}`, { method: "PATCH", json: { notes } });
                  setNotes(null);
                }, "Saved")
              }
            >
              Save notes
            </Button>
          )}
        </div>
        {canAct && others.length > 0 && (
          <div>
            <div className="mb-1 text-xs uppercase text-muted-foreground">Merge another contact into this one</div>
            <div className="flex gap-2">
              <NativeSelect
                data-testid="merge-select"
                className="min-w-0 flex-1"
                value={mergeId}
                onChange={(e) => setMergeId(e.target.value)}
                options={[
                  { value: "", label: "Choose contact…" },
                  ...others.map((o) => ({
                    value: String(o.id),
                    label: `${o.display_name} (${o.identities.map((i) => i.channel).join(", ")})`,
                  })),
                ]}
              />
              <Button
                size="sm"
                disabled={!mergeId}
                onClick={() =>
                  run(async () => {
                    await api(`/contacts/${id}/merge`, { json: { source_contact_id: Number(mergeId) } });
                    setMergeId("");
                    router.replace(`/contacts?id=${id}`);
                  }, "Contacts merged")
                }
              >
                Merge
              </Button>
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Identities, conversations, cases and consents move here. Opt-out wins.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Contacts() {
  const params = useSearchParams();
  const router = useRouter();
  const selected = params.get("id") ? Number(params.get("id")) : null;
  const [q, setQ] = useState("");
  const { data } = useSWR<ContactRow[]>(`/contacts${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  return (
    <div className="grid h-full grid-cols-[20rem_1fr]">
      <div className="flex flex-col border-r">
        <div className="border-b p-3">
          <h1 className="mb-2 font-semibold">Contacts</h1>
          <Input placeholder="Search name, phone, id…" value={q} onChange={(e) => setQ(e.target.value)} className="h-8" />
        </div>
        <div className="flex-1 overflow-y-auto">
          {data?.map((c) => (
            <button
              key={c.id}
              onClick={() => router.push(`/contacts?id=${c.id}`)}
              className={cn("block w-full border-b px-3 py-2 text-left hover:bg-muted/60", selected === c.id && "bg-muted")}
            >
              <div className="flex items-center gap-2">
                <span className="flex-1 truncate text-sm">{c.display_name}</span>
                <span className="text-[11px] text-muted-foreground">{timeAgo(c.last_message_at)}</span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {c.identities.map((i) => (
                  <ChannelBadge key={i.id} channel={i.channel} simulated={i.simulated} />
                ))}
                {c.opted_out && <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[11px] text-white">STOP</span>}
                {c.broadcast_opt_in && <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[11px] text-sky-900">subscribed</span>}
              </div>
            </button>
          ))}
        </div>
      </div>
      {selected ? (
        <Detail key={selected} id={selected} all={data ?? []} />
      ) : (
        <div className="flex items-center justify-center text-sm text-muted-foreground">Select a contact</div>
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
