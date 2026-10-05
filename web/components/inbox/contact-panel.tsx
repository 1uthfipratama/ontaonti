"use client";

import Link from "next/link";
import useSWR from "swr";

import { channelName, SeverityBadge } from "@/components/badges";
import { clock, timeAgo } from "@/lib/format";
import type { Case, Conversation } from "@/lib/types";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}

export function ContactPanel({ id }: { id: number }) {
  const { data: conv } = useSWR<Conversation>(`/conversations/${id}`);
  const { data: cases } = useSWR<Case[]>(`/cases?status=all&conversation_id=${id}`);
  const c = conv?.contact;
  if (!c) return <div className="border-l border-border bg-card" />;
  return (
    <div className="h-full space-y-6 overflow-y-auto border-l border-border bg-card p-5">
      <div>
        <Link href={`/contacts?id=${c.id}`} className="text-[15px] font-semibold hover:text-primary">
          {c.display_name}
        </Link>
        <div className="text-xs text-muted-foreground">Contact since {clock(c.created_at)}</div>
      </div>

      <Section title="Details">
        {c.phone && <Row label="Phone" value={c.phone} />}
        <Row label="Messages" value={c.opted_out ? <span className="text-destructive">Opted out</span> : "Active"} />
        <Row label="Broadcasts" value={c.broadcast_opt_in ? "Subscribed" : "Not subscribed"} />
      </Section>

      <Section title="Channels">
        {c.identities.map((i) => (
          <Row
            key={i.id}
            label={channelName(i.channel)}
            value={<span className="font-mono text-xs">{i.simulated ? "simulated" : i.external_id}</span>}
          />
        ))}
      </Section>

      <Section title="Cases">
        {cases?.length === 0 && <p className="text-sm text-muted-foreground">No cases.</p>}
        {cases?.map((k) => (
          <Link
            key={k.id}
            href={`/cases?id=${k.id}`}
            data-testid="panel-case"
            className="-mx-2 block rounded-md px-2 py-1.5 hover:bg-muted"
          >
            <div className="flex items-center justify-between gap-2">
              <SeverityBadge severity={k.severity} category={k.category} />
              <span className="text-xs text-muted-foreground">{timeAgo(k.created_at)}</span>
            </div>
            <div className="text-xs text-muted-foreground">
              #{k.id} · {k.status.toLowerCase()}
              {k.assigned_name ? ` · ${k.assigned_name}` : ""}
            </div>
          </Link>
        ))}
      </Section>

      {c.notes && (
        <Section title="Notes">
          <p className="whitespace-pre-wrap text-sm">{c.notes}</p>
        </Section>
      )}
    </div>
  );
}
