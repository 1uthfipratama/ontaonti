"use client";

import Link from "next/link";
import useSWR from "swr";

import { ChannelBadge, SeverityBadge } from "@/components/badges";
import { clock, timeAgo } from "@/lib/format";
import type { Case, Conversation } from "@/lib/types";

export function ContactPanel({ id }: { id: number }) {
  const { data: conv } = useSWR<Conversation>(`/conversations/${id}`);
  const { data: cases } = useSWR<Case[]>(`/cases?status=all&conversation_id=${id}`);
  const c = conv?.contact;
  if (!c) return null;
  return (
    <div className="h-full space-y-4 overflow-y-auto border-l p-4 text-sm">
      <div>
        <div className="text-xs uppercase text-muted-foreground">Contact</div>
        <Link href={`/contacts?id=${c.id}`} className="font-semibold hover:underline">
          {c.display_name}
        </Link>
        {c.phone && <div className="text-xs text-muted-foreground">{c.phone}</div>}
        <div className="text-xs text-muted-foreground">since {clock(c.created_at)}</div>
      </div>
      <div>
        <div className="mb-1 text-xs uppercase text-muted-foreground">Identities</div>
        <ul className="space-y-1">
          {c.identities.map((i) => (
            <li key={i.id} className="flex items-center gap-2">
              <ChannelBadge channel={i.channel} simulated={i.simulated} />
              <span className="truncate font-mono text-xs">{i.external_id}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="space-y-1 text-xs">
        <div>
          Messaging:{" "}
          {c.opted_out ? <b className="text-red-600">opted out (STOP)</b> : <span>active</span>}
        </div>
        <div>Broadcasts: {c.broadcast_opt_in ? "subscribed" : "not subscribed"}</div>
      </div>
      <div>
        <div className="mb-1 text-xs uppercase text-muted-foreground">Cases</div>
        {cases?.length === 0 && <p className="text-xs text-muted-foreground">None.</p>}
        <ul className="space-y-2">
          {cases?.map((k) => (
            <li key={k.id} className="rounded border p-2" data-testid="panel-case">
              <div className="flex items-center gap-1">
                <SeverityBadge severity={k.severity} category={k.category} />
                <span className="ml-auto text-[11px] text-muted-foreground">{timeAgo(k.created_at)}</span>
              </div>
              <div className="mt-1 text-xs">
                #{k.id} · {k.status}
                {k.assigned_name ? ` · ${k.assigned_name}` : ""}
              </div>
              <Link href={`/cases?id=${k.id}`} className="text-xs text-primary hover:underline">
                Open case →
              </Link>
            </li>
          ))}
        </ul>
      </div>
      {c.notes && (
        <div>
          <div className="text-xs uppercase text-muted-foreground">Notes</div>
          <p className="whitespace-pre-wrap text-xs">{c.notes}</p>
        </div>
      )}
    </div>
  );
}
