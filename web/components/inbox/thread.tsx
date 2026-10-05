"use client";

import { useEffect, useRef, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { SendHorizontal } from "lucide-react";

import { channelName, SeverityBadge } from "@/components/badges";
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

  async function act(path: string, json: unknown) {
    try {
      await api(`/conversations/${id}/${path}`, { json });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  if (!conv) return <div className="bg-card p-6 text-sm text-muted-foreground">Loading…</div>;
  const staffName = (sid: number | null) => {
    const s = staff?.find((x) => x.id === sid);
    return s?.name || s?.email;
  };
  const sub = [
    channelName(conv.channel) + (conv.simulated ? " (simulated)" : ""),
    !conv.simulated ? `window ${windowLeft(conv.window_expires_at)}` : "",
    conv.assigned_to ? `assigned to ${staffName(conv.assigned_to)}` : "unassigned",
  ].filter(Boolean);

  return (
    <div className="flex h-full min-w-0 flex-col bg-card">
      <div className="flex items-center gap-4 border-b border-border px-5 py-3">
        <div className="min-w-[9rem] flex-1">
          <div className="truncate text-[15px] font-semibold" data-testid="thread-title">
            {conv.contact_name}
          </div>
          <div className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
            <SeverityBadge severity={conv.flag_severity} category={conv.flag_category} />
            <span className="truncate">{sub.join(" · ")}</span>
          </div>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground" title="Staff mode: the bot stays silent">
          <span className={conv.mode === "BOT" ? "font-semibold text-foreground" : ""}>Bot</span>
          <Switch
            data-testid="mode-switch"
            checked={conv.mode === "HUMAN"}
            disabled={!canAct}
            onCheckedChange={(v) => act("mode", { mode: v ? "HUMAN" : "BOT" })}
          />
          <span className={conv.mode === "HUMAN" ? "font-semibold text-foreground" : ""}>Staff</span>
        </label>
        {canAct && (
          <div className="flex shrink-0 items-center gap-1">
            <SummaryButton conversationId={id} />
            {conv.assigned_to !== me.id && (
              <Button size="sm" variant="ghost" onClick={() => act("assign", { staff_id: me.id })}>
                Assign to me
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => act("status", { status: conv.status === "OPEN" ? "RESOLVED" : "OPEN" })}
            >
              {conv.status === "OPEN" ? "Resolve" : "Reopen"}
            </Button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4" data-testid="thread">
        {messages?.map((m) => (
          <MessageBubble key={m.id} m={m} staffName={staffName(m.sender_staff_id)} />
        ))}
        <div ref={bottom} />
      </div>

      {canAct ? (
        <div className="border-t border-border px-5 py-3">
          {conv.opted_out && (
            <p className="mb-2 text-xs text-destructive">This contact replied STOP. Messages can&apos;t be sent.</p>
          )}
          <div className="flex items-end gap-2">
            <Textarea
              data-testid="reply-box"
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) send();
              }}
              placeholder={conv.mode === "BOT" ? "Reply as staff (the bot will step back)" : "Reply as staff"}
              className="max-h-40 min-h-10 flex-1"
            />
            <Button onClick={send} disabled={busy || !text.trim()} aria-label="Send">
              <SendHorizontal /> Send
            </Button>
          </div>
          <p className="mt-1.5 text-[11px] text-muted-foreground">Ctrl+Enter to send on the contact&apos;s channel.</p>
        </div>
      ) : (
        <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground">Read-only access.</div>
      )}
    </div>
  );
}
