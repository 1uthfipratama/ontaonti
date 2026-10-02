"use client";

import { useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, errorMessage } from "@/lib/api";
import { clock } from "@/lib/format";

type ChannelInfo = {
  enabled: boolean;
  configured: boolean;
  webhook_url: string;
  checks: Record<string, string>;
  last_webhook_at: string | null;
  graph_version?: string;
};
type Channels = {
  whatsapp: ChannelInfo;
  messenger: ChannelInfo;
  instagram: ChannelInfo;
  llm: { provider: string; key: string; answer_model: string; classifier_model: string };
  email_alerts: boolean;
};

function Dot({ ok, warn }: { ok: boolean; warn?: boolean }) {
  return <span className={`inline-block size-2 rounded-full ${ok ? "bg-emerald-500" : warn ? "bg-amber-500" : "bg-red-500"}`} />;
}

export function ChannelStatus() {
  const { data } = useSWR<Channels>("/settings/channels");
  const [check, setCheck] = useState<string>("");

  async function runCheck() {
    setCheck("checking…");
    try {
      const r = await api<{ ok: boolean; error?: string; phone?: Record<string, string> }>(
        "/settings/channels/whatsapp/check",
        { method: "POST" },
      );
      setCheck(r.ok ? `OK: ${r.phone?.display_phone_number ?? ""} ${r.phone?.verified_name ?? ""} (quality ${r.phone?.quality_rating ?? "?"})` : `Failed: ${r.error}`);
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
    <div className="grid gap-4 md:grid-cols-3">
      {rows.map(([name, ch]) => (
        <Card key={name} data-testid={`channel-${name.toLowerCase()}`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Dot ok={ch.enabled && ch.configured} warn={!ch.enabled} />
              {name}
              <span className="ml-auto text-xs font-normal text-muted-foreground">
                {!ch.enabled ? "disabled (feature flag)" : ch.configured ? "configured" : "not configured"}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div>
              <div className="text-muted-foreground">Webhook URL</div>
              <code className="break-all">{ch.webhook_url}</code>
            </div>
            <ul className="space-y-0.5">
              {Object.entries(ch.checks).map(([k, v]) => (
                <li key={k} className="flex items-center gap-1.5">
                  <Dot ok={v === "set"} /> <span className="font-mono">{k}</span>
                  <span className="text-muted-foreground">{v}</span>
                </li>
              ))}
            </ul>
            <div className="text-muted-foreground">
              Last webhook: {ch.last_webhook_at ? clock(ch.last_webhook_at) : "never"}
            </div>
            {name === "WhatsApp" && (
              <div className="space-y-1">
                <Button size="xs" variant="outline" onClick={runCheck}>
                  Test token (Graph API)
                </Button>
                {check && <p className="break-words">{check}</p>}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
      <Card className="md:col-span-3">
        <CardContent className="flex flex-wrap gap-6 pt-4 text-xs">
          <span>
            LLM provider: <b>{data.llm.provider}</b> (key {data.llm.key})
          </span>
          <span>Answer model: {data.llm.answer_model}</span>
          <span>Classifier: {data.llm.classifier_model}</span>
          <span>Email alerts: {data.email_alerts ? "on" : "off (no SMTP_HOST)"}</span>
        </CardContent>
      </Card>
    </div>
  );
}
