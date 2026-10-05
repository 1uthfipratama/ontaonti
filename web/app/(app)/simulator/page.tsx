"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Mic, Paperclip, SendHorizontal, Square } from "lucide-react";

import { channelName } from "@/components/badges";
import { MessageMedia, mediaSrc, textIsPlaceholder } from "@/components/message-media";
import { NativeSelect } from "@/components/native-select";
import { WaText } from "@/components/wa-text";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errorMessage } from "@/lib/api";
import { clock } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { Channel, Conversation, Message } from "@/lib/types";
import { cn } from "@/lib/utils";

const SAMPLES: { key: string; text: string; kind?: string }[] = [
  { key: "normal", text: "Halo kak, berapa lama sih pengobatan TBC?" },
  { key: "english", text: "Is TB contagious through sharing plates?" },
  { key: "mild", text: "Kenapa air kencing saya jadi warna oranye setelah minum obat?" },
  { key: "drug", text: "Mata dan kulit saya jadi kuning sejak minum obat TBC" },
  { key: "emergency", text: "Saya batuk darah banyak dan sesak napas berat" },
  { key: "selfharm", text: "Aku capek berobat terus, rasanya ingin mati saja" },
  { key: "adherence", text: "Obat saya habis dan saya mau berhenti pengobatan" },
  { key: "subscribe", text: "LANGGANAN" },
  { key: "stop", text: "STOP" },
  { key: "start", text: "MULAI" },
];

export default function SimulatorPage() {
  const t = useT();
  const { mutate } = useSWRConfig();
  const [channel, setChannel] = useState<Channel>("whatsapp");
  const [userId, setUserId] = useState("demo1");
  const [name, setName] = useState("Budi (simulasi)");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState<MediaRecorder | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const picker = useRef<HTMLInputElement>(null);

  const { data: sims } = useSWR<Conversation[]>("/simulator/conversations");
  const conv = useMemo(
    () => sims?.find((c) => c.channel === channel && c.identity?.external_id === `sim-${userId}`),
    [sims, channel, userId],
  );
  const { data: messages } = useSWR<Message[]>(conv ? `/conversations/${conv.id}/messages` : null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages?.length]);

  const refresh = () =>
    mutate((k) => typeof k === "string" && (k.startsWith("/simulator") || k.startsWith("/conversations")));

  async function sendFile(file: Blob, filename: string) {
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file, filename);
      form.append("channel", channel);
      form.append("user_id", userId);
      form.append("name", name);
      await api("/simulator/media", { form });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  }

  // Record a voice note in the browser (press once to start, again to send).
  async function toggleRecording() {
    if (recording) {
      recording.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setRecording(null);
        const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
        if (blob.size > 0) sendFile(blob, "pesan-suara.webm");
      };
      rec.start();
      setRecording(rec);
    } catch {
      toast.error(t("sim.micDenied"));
    }
  }

  async function send(body: string, kind = "text") {
    if (kind === "text" && !body.trim()) return;
    setBusy(true);
    try {
      await api("/simulator/messages", { json: { channel, user_id: userId, name, text: body, kind } });
      setText("");
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid h-full grid-rows-[minmax(0,1fr)] grid-cols-[15rem_minmax(0,1fr)] xl:grid-cols-[19rem_minmax(0,1fr)]">
      <div className="space-y-6 overflow-y-auto border-r border-border bg-card p-5">
        <p className="text-sm text-muted-foreground">{t("sim.intro")}</p>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">{t("sim.channel")}</Label>
            <NativeSelect
              data-testid="sim-channel"
              className="w-full"
              value={channel}
              onChange={(e) => setChannel(e.target.value as Channel)}
              options={[
                { value: "whatsapp", label: "WhatsApp" },
                { value: "messenger", label: "Messenger" },
                { value: "instagram", label: "Instagram" },
              ]}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="uid" className="text-xs text-muted-foreground">{t("sim.userId")}</Label>
            <Input
              id="uid"
              data-testid="sim-user"
              value={userId}
              onChange={(e) => setUserId(e.target.value.replace(/[^A-Za-z0-9_.-]/g, ""))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="uname" className="text-xs text-muted-foreground">{t("sim.name")}</Label>
            <Input id="uname" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        <div>
          <div className="mb-1.5 text-xs font-semibold text-muted-foreground">{t("sim.quick")}</div>
          <div className="-mx-2">
            {SAMPLES.map((s) => (
              <button
                key={s.key}
                disabled={busy}
                onClick={() => send(s.text, s.kind)}
                className="block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted disabled:opacity-50"
                title={s.text}
              >
                {t(`sim.s.${s.key}`)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-col items-center p-6">
        <div className="flex h-full w-full max-w-md flex-col overflow-hidden rounded-lg bg-card shadow-[0_2px_4px_rgba(39,43,50,0.06)]">
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            <div className="flex size-9 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">OE</div>
            <div className="flex-1 leading-tight">
              <div className="text-sm font-semibold">Onti Erlina</div>
              <div className="text-xs text-muted-foreground">
                {channelName(channel)} · {t("common.simulated")}
                {conv?.mode === "HUMAN" ? ` · ${t("inbox.staffHandling").toLowerCase()}` : ""}
              </div>
            </div>
            {conv && (
              <Link className="text-xs font-medium text-primary hover:underline" href={`/inbox?c=${conv.id}`}>
                {t("sim.openInbox")}
              </Link>
            )}
          </div>
          {conv?.mode === "HUMAN" && (
            <div className="flex items-center gap-3 border-b border-border bg-warning px-4 py-2 text-xs text-warning-foreground">
              <span className="flex-1">{t("sim.staffNotice")}</span>
              <button
                className="font-semibold underline-offset-2 hover:underline"
                onClick={async () => {
                  try {
                    await api(`/conversations/${conv.id}/mode`, { json: { mode: "BOT" } });
                    mutate((k) => typeof k === "string" && k.startsWith("/simulator"));
                  } catch (e) {
                    toast.error(errorMessage(e, t));
                  }
                }}
              >
                {t("sim.handBack")}
              </button>
            </div>
          )}
          <div className="flex-1 overflow-y-auto bg-muted px-4 py-4" data-testid="sim-thread">
            {!messages?.length && (
              <p className="mt-12 text-center text-sm text-muted-foreground">{t("sim.empty")}</p>
            )}
            {messages
              ?.filter((m) => m.direction !== "note")
              .map((m) => {
                const mine = m.direction === "in";
                return (
                  <div key={m.id} className={cn("my-2 flex", mine ? "justify-end" : "justify-start")}>
                    <div
                      data-testid={mine ? "sim-user-msg" : `sim-reply-${m.sender_type}`}
                      className={cn(
                        "max-w-[80%] rounded-lg px-3 py-2 text-sm leading-relaxed",
                        mine ? "bg-primary text-primary-foreground" : "bg-card text-foreground",
                      )}
                    >
                      {!mine && m.sender_type === "agent" && (
                        <div className="mb-0.5 text-xs font-semibold text-primary">{t("sim.staff")}</div>
                      )}
                      <MessageMedia m={m} />
                      {m.text && !(mediaSrc(m) && textIsPlaceholder(m)) && (
                        <div className="whitespace-pre-wrap break-words">
                          <WaText text={m.text} />
                        </div>
                      )}
                      <div className={cn("mt-1 text-right text-[10px]", mine ? "text-white/70" : "text-muted-foreground")}>
                        {clock(m.created_at)}
                      </div>
                      {!mine && Array.isArray(m.meta?.buttons) && (
                        <div className="-mx-3 -mb-2 mt-2 flex border-t border-border">
                          {(m.meta.buttons as string[]).map((b) => (
                            <button
                              key={b}
                              disabled={busy}
                              onClick={() => send(b)}
                              data-testid="sim-button"
                              className="flex-1 py-2 text-center text-sm font-medium text-primary hover:bg-muted [&+&]:border-l [&+&]:border-border"
                            >
                              {b}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            <div ref={bottom} />
          </div>
          <form
            className="flex gap-2 border-t border-border p-3"
            onSubmit={(e) => {
              e.preventDefault();
              send(text);
            }}
          >
            <input
              ref={picker}
              type="file"
              hidden
              accept="image/*,audio/*,application/pdf"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) sendFile(f, f.name);
                e.target.value = "";
              }}
            />
            <Button type="button" variant="ghost" size="icon" onClick={() => picker.current?.click()} aria-label={t("thread.attach")} disabled={busy}>
              <Paperclip />
            </Button>
            <Input
              data-testid="sim-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={recording ? t("sim.recording") : t("sim.placeholder")}
              disabled={Boolean(recording)}
            />
            {!text.trim() && (
              <Button
                type="button"
                size="icon"
                variant={recording ? "destructive" : "ghost"}
                onClick={toggleRecording}
                aria-label={recording ? t("sim.stopRecording") : t("sim.record")}
                title={recording ? t("sim.stopRecording") : t("sim.record")}
                disabled={busy}
              >
                {recording ? <Square /> : <Mic />}
              </Button>
            )}
            <Button type="submit" size="icon" disabled={busy || !text.trim()} data-testid="sim-send" aria-label={t("thread.send")}>
              <SendHorizontal />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
