"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { SendHorizontal } from "lucide-react";

import { channelName } from "@/components/badges";
import { NativeSelect } from "@/components/native-select";
import { WaText } from "@/components/wa-text";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, errorMessage } from "@/lib/api";
import { clock } from "@/lib/format";
import type { Channel, Conversation, Message } from "@/lib/types";
import { cn } from "@/lib/utils";

const SAMPLES: { label: string; text: string; kind?: string }[] = [
  { label: "Normal question", text: "Halo kak, berapa lama sih pengobatan TBC?" },
  { label: "English question", text: "Is TB contagious through sharing plates?" },
  { label: "Mild side effect", text: "Kenapa air kencing saya jadi warna oranye setelah minum obat?" },
  { label: "Drug side effect (risky)", text: "Mata dan kulit saya jadi kuning sejak minum obat TBC" },
  { label: "Emergency (risky)", text: "Saya batuk darah banyak dan sesak napas berat" },
  { label: "Self-harm (risky)", text: "Aku capek berobat terus, rasanya ingin mati saja" },
  { label: "Stopping treatment", text: "Obat saya habis dan saya mau berhenti pengobatan" },
  { label: "Subscribe (LANGGANAN)", text: "LANGGANAN" },
  { label: "Opt out (STOP)", text: "STOP" },
  { label: "Opt back in (MULAI)", text: "MULAI" },
  { label: "Send a photo", text: "", kind: "image" },
];

export default function SimulatorPage() {
  const { mutate } = useSWRConfig();
  const [channel, setChannel] = useState<Channel>("whatsapp");
  const [userId, setUserId] = useState("demo1");
  const [name, setName] = useState("Budi (simulasi)");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const { data: sims } = useSWR<Conversation[]>("/simulator/conversations");
  const conv = useMemo(
    () => sims?.find((c) => c.channel === channel && c.identity?.external_id === `sim-${userId}`),
    [sims, channel, userId],
  );
  const { data: messages } = useSWR<Message[]>(conv ? `/conversations/${conv.id}/messages` : null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages?.length]);

  async function send(body: string, kind = "text") {
    if (kind === "text" && !body.trim()) return;
    setBusy(true);
    try {
      await api("/simulator/messages", { json: { channel, user_id: userId, name, text: body, kind } });
      setText("");
      mutate((k) => typeof k === "string" && (k.startsWith("/simulator") || k.startsWith("/conversations")));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid h-full grid-rows-[minmax(0,1fr)] grid-cols-[15rem_minmax(0,1fr)] xl:grid-cols-[19rem_minmax(0,1fr)]">
      <div className="space-y-6 overflow-y-auto border-r border-border bg-white p-5">
        <p className="text-sm text-muted-foreground">
          Chat as a fake user. Messages go through the same safety checks and bot as real channels;
          nothing is sent to Meta.
        </p>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Channel</Label>
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
            <Label htmlFor="uid" className="text-xs text-muted-foreground">Fake user id</Label>
            <Input
              id="uid"
              data-testid="sim-user"
              value={userId}
              onChange={(e) => setUserId(e.target.value.replace(/[^A-Za-z0-9_.-]/g, ""))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="uname" className="text-xs text-muted-foreground">Display name</Label>
            <Input id="uname" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        </div>
        <div>
          <div className="mb-1.5 text-xs font-semibold text-muted-foreground">Quick messages</div>
          <div className="-mx-2">
            {SAMPLES.map((s) => (
              <button
                key={s.label}
                disabled={busy}
                onClick={() => send(s.text, s.kind)}
                className="block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted disabled:opacity-50"
                title={s.text}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-col items-center p-6">
        <div className="flex h-full w-full max-w-md flex-col overflow-hidden rounded-lg bg-white shadow-[0_2px_4px_rgba(39,43,50,0.06)]">
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            <div className="flex size-9 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">OE</div>
            <div className="flex-1 leading-tight">
              <div className="text-sm font-semibold">Onti Erlani</div>
              <div className="text-xs text-muted-foreground">
                {channelName(channel)} · simulated{conv?.mode === "HUMAN" ? " · staff handling" : ""}
              </div>
            </div>
            {conv && (
              <Link className="text-xs font-medium text-primary hover:underline" href={`/inbox?c=${conv.id}`}>
                Open in inbox →
              </Link>
            )}
          </div>
          {conv?.mode === "HUMAN" && (
            <div className="flex items-center gap-3 border-b border-border bg-[#fff6d6] px-4 py-2 text-xs text-[#a14a0b]">
              <span className="flex-1">
                Staff is handling this chat (a risky message or a staff reply), so the bot stays silent.
              </span>
              <button
                className="font-semibold underline-offset-2 hover:underline"
                onClick={async () => {
                  try {
                    await api(`/conversations/${conv.id}/mode`, { json: { mode: "BOT" } });
                    mutate((k) => typeof k === "string" && k.startsWith("/simulator"));
                  } catch (e) {
                    toast.error(errorMessage(e));
                  }
                }}
              >
                Hand back to bot
              </button>
            </div>
          )}
          <div className="flex-1 overflow-y-auto bg-muted px-4 py-4" data-testid="sim-thread">
            {!messages?.length && (
              <p className="mt-12 text-center text-sm text-muted-foreground">Say hello to start a conversation.</p>
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
                        mine ? "bg-primary text-white" : "bg-white text-foreground",
                      )}
                    >
                      {!mine && m.sender_type === "agent" && (
                        <div className="mb-0.5 text-xs font-semibold text-primary">Staf</div>
                      )}
                      <div className="whitespace-pre-wrap break-words">
                        <WaText text={m.text} />
                      </div>
                      <div className={cn("mt-1 text-right text-[10px]", mine ? "text-white/70" : "text-muted-foreground")}>
                        {clock(m.created_at)}
                      </div>
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
            <Input
              data-testid="sim-input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Type a message as the user…"
            />
            <Button type="submit" size="icon" disabled={busy || !text.trim()} data-testid="sim-send" aria-label="Send">
              <SendHorizontal />
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
