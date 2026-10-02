"use client";

import { useEffect, useRef, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { ChannelBadge, ModeBadge, SeverityBadge } from "@/components/badges";
import { MessageBubble } from "@/components/message-bubble";
import { SummaryButton } from "@/components/inbox/summary-button";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { windowLeft } from "@/lib/format";
import { useCanAct, useStaff } from "@/lib/session";
import type { Conversation, Message, Staff } from "@/lib/types";

export function Thread({ id }: { id: number }) {
  const { mutate } = useSWRConfig();
  const me = useStaff();
  const canAct = useCanAct();
  const { data: conv } = useSWR<Conversation>(`/conversations/${id}`);
  const { data: messages } = useSWR<Message[]>(`/conversations/${id}/messages`);
  const { data: staff } = useSWR<Staff[]>("/staff");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages?.length]);

  useEffect(() => {
    if (conv && conv.unread_count > 0) {
      api(`/conversations/${id}/read`, { method: "POST" }).then(() =>
        mutate((k) => typeof k === "string" && k.startsWith("/conversations?")),
      );
    }
  }, [conv, id, mutate]);

  const refresh = () => mutate((k) => typeof k === "string" && k.startsWith("/conversations"));

  async function send() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await api(`/conversations/${id}/messages`, { json: { text } });
      setText("");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function toggleMode(human: boolean) {
    try {
      await api(`/conversations/${id}/mode`, { json: { mode: human ? "HUMAN" : "BOT" } });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  async function setStatus(status: "OPEN" | "RESOLVED") {
    await api(`/conversations/${id}/status`, { json: { status } });
    refresh();
  }

  async function assignMe() {
    await api(`/conversations/${id}/assign`, { json: { staff_id: me.id } });
    refresh();
  }

  if (!conv) return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  const staffName = (sid: number | null) => staff?.find((s) => s.id === sid)?.name || staff?.find((s) => s.id === sid)?.email;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
        <div className="mr-2">
          <div className="font-semibold" data-testid="thread-title">{conv.contact_name}</div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <ChannelBadge channel={conv.channel} simulated={conv.simulated} />
            <ModeBadge mode={conv.mode} />
            <SeverityBadge severity={conv.flag_severity} category={conv.flag_category} />
            {!conv.simulated && <span>· window {windowLeft(conv.window_expires_at)}</span>}
            {conv.assigned_to && <span>· assigned to {staffName(conv.assigned_to)}</span>}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs" title="Human mode: the bot stays silent">
            Bot
            <Switch
              data-testid="mode-switch"
              checked={conv.mode === "HUMAN"}
              disabled={!canAct}
              onCheckedChange={(v) => toggleMode(Boolean(v))}
            />
            Human
          </label>
          {canAct && <SummaryButton conversationId={id} />}
          {canAct && conv.assigned_to !== me.id && (
            <Button size="sm" variant="outline" onClick={assignMe}>
              Assign to me
            </Button>
          )}
          {canAct &&
            (conv.status === "OPEN" ? (
              <Button size="sm" variant="outline" onClick={() => setStatus("RESOLVED")}>
                Resolve
              </Button>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setStatus("OPEN")}>
                Reopen
              </Button>
            ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3" data-testid="thread">
        {messages?.map((m) => (
          <MessageBubble key={m.id} m={m} staffName={staffName(m.sender_staff_id)} />
        ))}
        <div ref={bottom} />
      </div>
      {canAct ? (
        <div className="border-t p-3">
          {conv.opted_out && (
            <p className="mb-2 text-xs text-red-600">This contact replied STOP. Messages can&apos;t be sent.</p>
          )}
          <div className="flex gap-2">
            <Textarea
              data-testid="reply-box"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send();
              }}
              placeholder={conv.mode === "BOT" ? "Reply as staff (switches to Human mode)…" : "Reply as staff…"}
              className="min-h-16 flex-1"
            />
            <Button onClick={send} disabled={busy || !text.trim()} className="self-end">
              Send
            </Button>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">Ctrl+Enter to send. Sent on the contact&apos;s channel.</p>
        </div>
      ) : (
        <div className="border-t p-3 text-xs text-muted-foreground">Read-only (reviewer).</div>
      )}
    </div>
  );
}
