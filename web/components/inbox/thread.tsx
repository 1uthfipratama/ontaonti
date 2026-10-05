"use client";

import { useEffect, useRef, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Loader2, SendHorizontal, Wand2 } from "lucide-react";

import { channelName, SeverityBadge } from "@/components/badges";
import { MessageBubble } from "@/components/message-bubble";
import { LabelPicker } from "@/components/inbox/label-picker";
import { SummaryButton } from "@/components/inbox/summary-button";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { windowLeft } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useCanAct, useStaff } from "@/lib/session";
import type { Conversation, Message, SavedReply, Staff } from "@/lib/types";
import { cn } from "@/lib/utils";

type Tab = "reply" | "note";

export function Thread({ id }: { id: number }) {
  const t = useT();
  const { mutate } = useSWRConfig();
  const me = useStaff();
  const canAct = useCanAct();
  const { data: conv } = useSWR<Conversation>(`/conversations/${id}`);
  const { data: messages } = useSWR<Message[]>(`/conversations/${id}/messages`);
  const { data: staff } = useSWR<Staff[]>("/staff");
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

  async function act(path: string, json: unknown) {
    try {
      await api(`/conversations/${id}/${path}`, { json });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  if (!conv) return <div className="bg-card p-6 text-sm text-muted-foreground">{t("common.loading")}</div>;
  const staffName = (sid: number | null) => {
    const s = staff?.find((x) => x.id === sid);
    return s?.name || s?.email;
  };
  const sub = [
    channelName(conv.channel) + (conv.simulated ? ` (${t("channel.simulated")})` : ""),
    !conv.simulated ? windowLeft(conv.window_expires_at, t) : "",
    conv.assigned_to ? t("thread.assignedTo", { name: staffName(conv.assigned_to) ?? "" }) : t("thread.unassigned"),
    ...conv.labels.map((l) => l.name),
  ].filter(Boolean);

  return (
    <div className="flex h-full min-w-0 flex-col bg-card">
      <div className="flex items-center gap-3 border-b border-border px-5 py-3">
        <div className="min-w-[9rem] flex-1">
          <div className="truncate text-[15px] font-semibold" data-testid="thread-title">
            {conv.contact_name}
          </div>
          <div className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
            <SeverityBadge severity={conv.flag_severity} category={conv.flag_category} />
            <span className="truncate">{sub.join(" · ")}</span>
          </div>
        </div>
        <label className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground" title={t("thread.modeHint")}>
          <span className={conv.mode === "BOT" ? "font-semibold text-foreground" : ""}>{t("thread.bot")}</span>
          <Switch
            data-testid="mode-switch"
            checked={conv.mode === "HUMAN"}
            disabled={!canAct}
            onCheckedChange={(v) => act("mode", { mode: v ? "HUMAN" : "BOT" })}
          />
          <span className={conv.mode === "HUMAN" ? "font-semibold text-foreground" : ""}>{t("thread.staff")}</span>
        </label>
        {canAct && (
          <div className="flex shrink-0 items-center gap-0.5">
            <SummaryButton conversationId={id} />
            <LabelPicker conv={conv} />
            {conv.assigned_to !== me.id && (
              <Button size="sm" variant="ghost" onClick={() => act("assign", { staff_id: me.id })}>
                {t("thread.assignMe")}
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => act("status", { status: conv.status === "OPEN" ? "RESOLVED" : "OPEN" })}
            >
              {conv.status === "OPEN" ? t("thread.resolve") : t("thread.reopen")}
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
        <Composer conv={conv} onSent={refresh} />
      ) : (
        <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground">{t("common.readOnly")}</div>
      )}
    </div>
  );
}

function Composer({ conv, onSent }: { conv: Conversation; onSent: () => void }) {
  const t = useT();
  const [tab, setTab] = useState<Tab>("reply");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [pick, setPick] = useState(0);
  const box = useRef<HTMLTextAreaElement>(null);
  const { data: replies } = useSWR<SavedReply[]>("/saved-replies");

  // "/" at the start of the box (or after whitespace) opens the saved-reply list.
  const slash = text.match(/(?:^|\s)\/([\w-]*)$/);
  const matches =
    tab === "reply" && slash
      ? (replies ?? []).filter(
          (r) => r.shortcut.startsWith(slash[1].toLowerCase()) || r.title.toLowerCase().includes(slash[1].toLowerCase()),
        )
      : [];

  function insert(r: SavedReply) {
    const body = r.body.replaceAll("{nama}", conv.contact_name).replaceAll("{name}", conv.contact_name);
    setText(text.replace(/\/[\w-]*$/, body));
    setPick(0);
    box.current?.focus();
  }

  async function submit() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      if (tab === "note") await api(`/conversations/${conv.id}/notes`, { json: { text } });
      else await api(`/conversations/${conv.id}/messages`, { json: { text } });
      setText("");
    } catch (e) {
      toast.error(errorMessage(e, t));
    } finally {
      setBusy(false);
      onSent();
    }
  }

  async function suggest() {
    setDrafting(true);
    try {
      const r = await api<{ text: string }>(`/conversations/${conv.id}/suggest`, { method: "POST" });
      setTab("reply");
      setText(r.text);
      box.current?.focus();
    } catch (e) {
      toast.error(errorMessage(e, t));
    } finally {
      setDrafting(false);
    }
  }

  const note = tab === "note";
  return (
    <div className={cn("border-t border-border px-5 pt-2 pb-3", note && "bg-warning/10")}>
      <div className="mb-2 flex items-center gap-1 text-[13px]">
        {(["reply", "note"] as const).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setTab(k)}
            data-testid={`tab-${k}`}
            className={cn(
              "rounded-md px-2.5 py-1 font-medium",
              tab === k ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {k === "reply" ? t("thread.tabReply") : t("thread.tabNote")}
          </button>
        ))}
        <span className="flex-1" />
        {!note && (
          <button
            type="button"
            onClick={suggest}
            disabled={drafting}
            data-testid="suggest-button"
            className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-60"
          >
            {drafting ? <Loader2 className="size-3.5 animate-spin" /> : <Wand2 className="size-3.5" />}
            {drafting ? t("thread.suggesting") : t("thread.suggest")}
          </button>
        )}
      </div>
      {!note && conv.opted_out && <p className="mb-2 text-xs text-destructive">{t("thread.optedOut")}</p>}
      <div className="relative flex items-end gap-2">
        {matches.length > 0 && (
          <div
            className="absolute bottom-full left-0 z-20 mb-2 max-h-64 w-full max-w-md overflow-y-auto rounded-lg bg-popover p-1.5 shadow-[0_10px_15px_-3px_rgba(0,0,0,0.12)] ring-1 ring-border"
            data-testid="saved-reply-menu"
          >
            {matches.map((r, i) => (
              <button
                key={r.id}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  insert(r);
                }}
                className={cn(
                  "block w-full rounded-md px-2.5 py-1.5 text-left",
                  i === pick % matches.length ? "bg-muted" : "hover:bg-muted",
                )}
              >
                <div className="flex items-baseline gap-2 text-sm">
                  <span className="font-mono text-xs text-primary">/{r.shortcut}</span>
                  <span className="truncate font-medium">{r.title}</span>
                </div>
                <div className="truncate text-xs text-muted-foreground">{r.body}</div>
              </button>
            ))}
          </div>
        )}
        <Textarea
          ref={box}
          data-testid="reply-box"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setPick(0);
          }}
          onKeyDown={(e) => {
            if (matches.length) {
              if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                setPick((p) => (p + (e.key === "ArrowDown" ? 1 : matches.length - 1)) % matches.length);
                return;
              }
              if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                insert(matches[pick % matches.length]);
                return;
              }
            }
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit();
          }}
          placeholder={
            note
              ? t("thread.notePlaceholder")
              : conv.mode === "BOT"
                ? t("thread.replyPlaceholderBot")
                : t("thread.replyPlaceholder")
          }
          className="max-h-40 min-h-10 flex-1 bg-card"
        />
        <Button onClick={submit} disabled={busy || !text.trim()} aria-label={note ? t("thread.addNote") : t("thread.send")}>
          {!note && <SendHorizontal />} {note ? t("thread.addNote") : t("thread.send")}
        </Button>
      </div>
      <p className="mt-1.5 text-[11px] text-muted-foreground">{t("thread.sendHint")}</p>
    </div>
  );
}
