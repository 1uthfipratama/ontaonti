"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { ChannelBadge, ModeBadge } from "@/components/badges";
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
  { label: "English", text: "Is TB contagious through sharing plates?" },
  { label: "Side effect (low)", text: "Kenapa air kencing saya jadi warna oranye setelah minum obat?" },
  { label: "Risky: adverse drug", text: "Mata dan kulit saya jadi kuning sejak minum obat TBC" },
  { label: "Risky: emergency", text: "Saya batuk darah banyak dan sesak napas berat" },
  { label: "Risky: self-harm", text: "Aku capek berobat terus, rasanya ingin mati saja" },
  { label: "Adherence", text: "Obat saya habis dan saya mau berhenti pengobatan" },
  { label: "Subscribe", text: "LANGGANAN" },
  { label: "Opt out", text: "STOP" },
  { label: "Opt back in", text: "MULAI" },
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
    <div className="grid h-full grid-cols-[18rem_1fr]">
      <div className="space-y-4 overflow-y-auto border-r p-4">
        <div>
          <h1 className="font-semibold">Simulator</h1>
          <p className="text-xs text-muted-foreground">
            Chat as a fake user. Messages go through the same worker, safety checks and bot as real
            channels; nothing is sent to Meta.
          </p>
        </div>
        <div className="space-y-1.5">
          <Label>Channel label</Label>
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
          <Label htmlFor="uid">Fake user id</Label>
          <Input id="uid" data-testid="sim-user" value={userId} onChange={(e) => setUserId(e.target.value.replace(/[^A-Za-z0-9_.-]/g, ""))} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="uname">Display name</Label>
          <Input id="uname" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <div className="mb-1.5 text-xs font-medium uppercase text-muted-foreground">Quick messages</div>
          <div className="flex flex-col gap-1">
            {SAMPLES.map((s) => (
              <button
                key={s.label}
                disabled={busy}
                onClick={() => send(s.text, s.kind)}
                className="rounded border px-2 py-1 text-left text-xs hover:bg-muted"
                title={s.text}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-col items-center bg-muted/30 p-4">
        <div className="flex h-full w-full max-w-md flex-col overflow-hidden rounded-2xl border bg-background shadow">
          <div className="flex items-center gap-2 border-b px-4 py-2">
            <div className="flex-1">
              <div className="text-sm font-semibold">Onti Erlani</div>
              <div className="flex gap-1">
                <ChannelBadge channel={channel} simulated />
                {conv && <ModeBadge mode={conv.mode} />}
              </div>
            </div>
            {conv && (
              <Link className="text-xs text-primary hover:underline" href={`/inbox?c=${conv.id}`}>
                Open in inbox →
              </Link>
            )}
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-3" data-testid="sim-thread">
            {!messages?.length && (
              <p className="mt-10 text-center text-xs text-muted-foreground">Say hello to start a conversation.</p>
            )}
            {messages
              ?.filter((m) => m.direction !== "note")
              .map((m) => {
                const mine = m.direction === "in";
                return (
                  <div key={m.id} className={cn("my-1.5 flex", mine ? "justify-end" : "justify-start")}>
                    <div
                      data-testid={mine ? "sim-user-msg" : `sim-reply-${m.sender_type}`}
                      className={cn(
                        "max-w-[80%] rounded-2xl px-3 py-2 text-sm",
                        mine ? "rounded-br-sm bg-emerald-200 dark:bg-emerald-900" : "rounded-bl-sm bg-muted",
                      )}
                    >
                      {!mine && m.sender_type === "agent" && (
                        <div className="text-[10px] font-semibold text-emerald-700">Staf</div>
                      )}
                      <div className="whitespace-pre-wrap break-words">
                        <WaText text={m.text} />
                      </div>
                      <div className="mt-0.5 text-right text-[10px] text-muted-foreground">{clock(m.created_at)}</div>
                    </div>
                  </div>
                );
              })}
            <div ref={bottom} />
          </div>
          <form
            className="flex gap-2 border-t p-2"
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
            <Button type="submit" disabled={busy || !text.trim()} data-testid="sim-send">
              Send
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
