"use client";

import { useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { clock } from "@/lib/format";
import { cn } from "@/lib/utils";

type ChannelInfo = {
  enabled: boolean;
  configured: boolean;
  webhook_url: string;
  checks: Record<string, string>;
  last_webhook_at: string | null;
};
type Channels = {
  whatsapp: ChannelInfo;
  messenger: ChannelInfo;
  instagram: ChannelInfo;
  llm: { provider: string; key: string; answer_model: string; classifier_model: string };
  email_alerts: boolean;
};

function state(ch: ChannelInfo): { text: string; ok: boolean } {
  if (!ch.enabled) return { text: "Off", ok: false };
  return ch.configured ? { text: "Connected", ok: true } : { text: "Not configured", ok: false };
}

export function ChannelStatus() {
  const { data } = useSWR<Channels>("/settings/channels");
  const [check, setCheck] = useState("");

  async function runCheck() {
    setCheck("Checking…");
    try {
      const r = await api<{ ok: boolean; error?: string; phone?: Record<string, string> }>(
        "/settings/channels/whatsapp/check",
        { method: "POST" },
      );
      setCheck(
        r.ok
          ? `Token works: ${r.phone?.display_phone_number ?? ""} ${r.phone?.verified_name ?? ""}`
          : `Failed: ${r.error}`,
      );
    } catch (e) {
      toast.error(errorMessage(e));
      setCheck("");
    }
  }

  if (!data) return null;
  const rows: [string, ChannelInfo][] = [
    ["WhatsApp", data.whatsapp],
    ["Messenger", data.messenger],
    ["Instagram", data.instagram],
  ];
  return (
    <div className="rounded-lg bg-white">
      {rows.map(([name, ch], i) => {
        const st = state(ch);
        const missing = Object.entries(ch.checks).filter(([, v]) => v === "missing").map(([k]) => k);
        const detected = Object.entries(ch.checks).filter(([, v]) => v.startsWith("detected"));
        return (
          <div
            key={name}
            data-testid={`channel-${name.toLowerCase()}`}
            className={cn("grid gap-4 px-5 py-4 md:grid-cols-[10rem_1fr_auto]", i > 0 && "border-t border-[#f0f1f3]")}
          >
            <div>
              <div className="text-sm font-semibold">{name}</div>
              <div className={cn("mt-0.5 text-xs", st.ok ? "text-[#186f4a]" : "text-muted-foreground")}>{st.text}</div>
            </div>
            <div className="min-w-0 space-y-1 text-xs text-muted-foreground">
              <div>
                Webhook <code className="break-all text-foreground">{ch.webhook_url}</code>
              </div>
              {missing.length > 0 && <div>Missing: {missing.join(", ")}</div>}
              {detected.map(([k, v]) => (
                <div key={k}>
                  {k} {v.replace("detected", "learned from webhook:")}
                </div>
              ))}
              <div>Last webhook: {ch.last_webhook_at ? clock(ch.last_webhook_at) : "never"}</div>
              {name === "WhatsApp" && check && <div className="text-foreground">{check}</div>}
            </div>
            <div>
              {name === "WhatsApp" && (
                <Button size="sm" variant="outline" onClick={runCheck}>
                  Test token
                </Button>
              )}
            </div>
          </div>
        );
      })}
      <div className="grid gap-x-8 gap-y-1 border-t border-[#f0f1f3] px-5 py-4 text-xs text-muted-foreground md:grid-cols-4">
        <span>
          LLM: <span className="text-foreground">{data.llm.provider}</span> (key {data.llm.key})
        </span>
        <span>
          Answers: <span className="text-foreground">{data.llm.answer_model}</span>
        </span>
        <span>
          Classifier: <span className="text-foreground">{data.llm.classifier_model}</span>
        </span>
        <span>
          Email alerts: <span className="text-foreground">{data.email_alerts ? "on" : "off"}</span>
        </span>
      </div>
    </div>
  );
}
