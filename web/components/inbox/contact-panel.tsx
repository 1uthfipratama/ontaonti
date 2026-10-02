"use client";

import Link from "next/link";
import useSWR from "swr";

import { ChannelBadge } from "@/components/badges";
import { clock } from "@/lib/format";
import type { Conversation } from "@/lib/types";

export function ContactPanel({ id }: { id: number }) {
  const { data: conv } = useSWR<Conversation>(`/conversations/${id}`);
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
      {c.notes && (
        <div>
          <div className="text-xs uppercase text-muted-foreground">Notes</div>
          <p className="whitespace-pre-wrap text-xs">{c.notes}</p>
        </div>
      )}
    </div>
  );
}
