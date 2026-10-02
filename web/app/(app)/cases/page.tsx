"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { ChannelBadge, SeverityBadge } from "@/components/badges";
import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { clock, timeAgo } from "@/lib/format";
import { useCanAct } from "@/lib/session";
import type { Case } from "@/lib/types";
import { cn } from "@/lib/utils";

function CaseDetail({ id }: { id: number }) {
  const { mutate } = useSWRConfig();
  const canAct = useCanAct();
  const { data: c } = useSWR<Case & { conversation_mode: string }>(`/cases/${id}`);
  const [note, setNote] = useState("");
  const refresh = () => mutate((k) => typeof k === "string" && (k.startsWith("/cases") || k.startsWith("/notifications")));

  async function act(path: string, json?: unknown) {
    try {
      await api(`/cases/${id}${path}`, { method: "POST", json });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  if (!c) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  return (
    <div className="h-full space-y-4 overflow-y-auto p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">Case #{c.id}</h2>
        <SeverityBadge severity={c.severity} category={c.category} />
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{c.status}</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">Contact</div>
          <div className="flex items-center gap-2">
            {c.contact_name} <ChannelBadge channel={c.channel} />
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Opened</div>
          {clock(c.created_at)}
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Assigned</div>
          {c.assigned_name ?? "—"}
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Conversation mode</div>
          {c.conversation_mode}
        </div>
      </div>
      {c.trigger_text && (
        <div className="rounded-lg border-l-4 border-red-500 bg-muted/50 p-3 text-sm">
          <div className="mb-1 text-xs text-muted-foreground">Message that triggered it</div>
          {c.trigger_text}
        </div>
      )}
      <div className="text-xs text-muted-foreground whitespace-pre-wrap">Reason: {c.reason}</div>
      <div className="flex flex-wrap gap-2">
        <Link href={`/inbox?c=${c.conversation_id}`}>
          <Button size="sm" variant="outline">Open conversation</Button>
        </Link>
        {canAct && c.status !== "RESOLVED" && (
          <>
            {c.status === "OPEN" && (
              <Button size="sm" onClick={() => act("/claim")} data-testid="claim-case">
                Claim
              </Button>
            )}
            {c.status === "CLAIMED" && (
              <Button size="sm" variant="outline" onClick={() => act("/status", { status: "OPEN" })}>
                Unclaim
              </Button>
            )}
            <Button size="sm" onClick={() => act("/resolve", { return_to_bot: true })} data-testid="resolve-case">
              Resolve &amp; return to bot
            </Button>
            <Button size="sm" variant="outline" onClick={() => act("/resolve", { return_to_bot: false })}>
              Resolve (stay human)
            </Button>
          </>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold">Notes</h3>
        <ul className="space-y-2">
          {c.notes?.map((n) => (
            <li key={n.id} className="rounded border p-2 text-sm">
              <div className="text-[11px] text-muted-foreground">
                {n.author} · {clock(n.created_at)}
              </div>
              <div className="whitespace-pre-wrap">{n.text}</div>
            </li>
          ))}
          {c.notes?.length === 0 && <li className="text-xs text-muted-foreground">No notes yet.</li>}
        </ul>
        {canAct && (
          <div className="mt-2 flex gap-2">
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note…" className="min-h-14" />
            <Button
              size="sm"
              className="self-end"
              disabled={!note.trim()}
              onClick={async () => {
                await act("/notes", { text: note });
                setNote("");
              }}
            >
              Add
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function Cases() {
  const params = useSearchParams();
  const router = useRouter();
  const selected = params.get("id") ? Number(params.get("id")) : null;
  const [status, setStatus] = useState("active");
  const { data } = useSWR<Case[]>(`/cases?status=${status}`);
  return (
    <div className="grid h-full grid-cols-[24rem_1fr]">
      <div className="flex flex-col border-r">
        <div className="flex items-center gap-2 border-b p-3">
          <h1 className="flex-1 font-semibold">Cases</h1>
          <NativeSelect
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            options={[
              { value: "active", label: "Open + claimed" },
              { value: "OPEN", label: "Unclaimed" },
              { value: "CLAIMED", label: "Claimed" },
              { value: "RESOLVED", label: "Resolved" },
              { value: "all", label: "All" },
            ]}
          />
        </div>
        <div className="flex-1 overflow-y-auto" data-testid="case-list">
          {data?.length === 0 && <p className="p-3 text-sm text-muted-foreground">No cases. 🎉</p>}
          {data?.map((c) => (
            <button
              key={c.id}
              onClick={() => router.push(`/cases?id=${c.id}`)}
              className={cn(
                "block w-full border-b px-3 py-2 text-left hover:bg-muted/60",
                selected === c.id && "bg-muted",
              )}
            >
              <div className="flex items-center gap-2">
                <SeverityBadge severity={c.severity} category={c.category} />
                <span className="ml-auto text-[11px] text-muted-foreground">{timeAgo(c.created_at)}</span>
              </div>
              <div className="mt-1 truncate text-sm">{c.contact_name}</div>
              <div className="truncate text-xs text-muted-foreground">{c.trigger_text}</div>
              <div className="mt-1 text-[11px] text-muted-foreground">
                #{c.id} · {c.status}
                {c.assigned_name ? ` · ${c.assigned_name}` : ""}
              </div>
            </button>
          ))}
        </div>
      </div>
      {selected ? (
        <CaseDetail key={selected} id={selected} />
      ) : (
        <div className="flex items-center justify-center text-sm text-muted-foreground">Select a case</div>
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
