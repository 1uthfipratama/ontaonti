"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { clock, idr } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Template = {
  id: number;
  name: string;
  language: string;
  category: string;
  status: string;
  body_text: string;
  variable_count: number;
  source: string;
};
type Stats = { sent: number; delivered: number; read: number; failed: number; pending: number; skipped: number };
type Broadcast = {
  id: number;
  name: string;
  template: Template | null;
  status: string;
  recipient_count: number;
  rate_idr: number;
  est_cost_idr: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  stats: Stats;
  recipients?: {
    id: number;
    contact_name: string;
    status: string;
    attempts: number;
    error: string | null;
    sent_at: string | null;
    delivered_at: string | null;
    read_at: string | null;
  }[];
};
type Estimate = {
  recipients: number;
  sample: string[];
  simulated: number;
  rate_idr: number;
  total_idr: number;
  category: string;
  preview: string;
  template_messages_this_month: number;
  free_tier: number;
};

function Templates() {
  const t = useT();
  const { mutate } = useSWRConfig();
  const { data } = useSWR<Template[]>("/templates");
  const [form, setForm] = useState({ name: "", language: "id", category: "UTILITY", body_text: "" });

  async function sync() {
    try {
      const r = await api<{ synced: number }>("/templates/sync", { method: "POST" });
      toast.success(t("bc.synced", { n: r.synced }));
      mutate("/templates");
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }
  async function register() {
    try {
      await api("/templates", { json: form });
      toast.success(t("bc.registered"));
      setForm({ ...form, name: "", body_text: "" });
      mutate("/templates");
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
      <Card>
        <CardHeader className="flex flex-row items-center">
          <CardTitle className="flex-1">{t("bc.templates")}</CardTitle>
          <Button size="sm" variant="outline" onClick={sync}>
            {t("bc.sync")}
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("bc.name")}</TableHead>
                <TableHead>{t("bc.lang")}</TableHead>
                <TableHead>{t("bc.category")}</TableHead>
                <TableHead>{t("bc.status")}</TableHead>
                <TableHead>{t("bc.body")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.map((x) => (
                <TableRow key={x.id}>
                  <TableCell className="font-mono text-xs">{x.name}</TableCell>
                  <TableCell className="text-xs">{x.language}</TableCell>
                  <TableCell className="text-xs">{x.category}</TableCell>
                  <TableCell className="text-xs">{x.status}</TableCell>
                  <TableCell className="max-w-sm truncate text-xs">{x.body_text}</TableCell>
                </TableRow>
              ))}
              {data?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-xs text-muted-foreground">
                    {t("bc.noTemplates")}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("bc.register")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-[11px] text-muted-foreground">{t("bc.registerHint")}</p>
          <Input placeholder="nama_template" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="flex gap-2">
            <Input className="w-24" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
            <NativeSelect
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              options={["UTILITY", "MARKETING", "AUTHENTICATION"].map((c) => ({ value: c, label: c }))}
            />
          </div>
          <Textarea placeholder="{{1}}, {{2}}…" value={form.body_text} onChange={(e) => setForm({ ...form, body_text: e.target.value })} />
          <Button size="sm" onClick={register} disabled={!form.name || !form.body_text}>
            {t("bc.registerButton")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function Composer({ onCreated }: { onCreated: (id: number) => void }) {
  const t = useT();
  const { data: templates } = useSWR<Template[]>("/templates");
  const usable = templates?.filter((x) => ["APPROVED", "MANUAL"].includes(x.status)) ?? [];
  const [templateId, setTemplateId] = useState("");
  const [name, setName] = useState("");
  const [vars, setVars] = useState<string[]>([]);
  const [est, setEst] = useState<Estimate | null>(null);
  const tpl = usable.find((x) => String(x.id) === templateId);

  function chooseTemplate(id: string) {
    const next = usable.find((x) => String(x.id) === id);
    setTemplateId(id);
    // One input per {{n}}; the first defaults to the contact's name.
    setVars(next ? Array.from({ length: next.variable_count }, (_, i) => (i === 0 ? "{{name}}" : "")) : []);
    setEst(null);
  }

  async function estimate() {
    try {
      setEst(await api<Estimate>("/broadcasts/estimate", { json: { template_id: Number(templateId), variables: vars } }));
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }
  async function createAndSend() {
    if (!est) return;
    if (!confirm(t("bc.confirm", { name: tpl?.name ?? "", n: est.recipients, cost: idr(est.total_idr) }))) return;
    try {
      const bc = await api<Broadcast>("/broadcasts", { json: { template_id: Number(templateId), variables: vars, name } });
      await api(`/broadcasts/${bc.id}/send`, { method: "POST" });
      toast.success(t("bc.queued"));
      onCreated(bc.id);
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("bc.new")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>{t("bc.template")}</Label>
            <NativeSelect
              data-testid="bc-template"
              className="w-full"
              value={templateId}
              onChange={(e) => chooseTemplate(e.target.value)}
              options={[
                { value: "", label: t("bc.chooseTemplate") },
                ...usable.map((x) => ({ value: String(x.id), label: `${x.name} (${x.language}, ${x.category})` })),
              ]}
            />
          </div>
          {tpl && <p className="rounded-lg bg-muted px-3 py-2 text-sm whitespace-pre-wrap">{tpl.body_text}</p>}
          {vars.map((v, i) => (
            <div key={i} className="space-y-1">
              <Label className="text-xs">{`{{${i + 1}}}`}</Label>
              <Input
                value={v}
                onChange={(e) => {
                  setVars(vars.map((x, j) => (j === i ? e.target.value : x)));
                  setEst(null); // estimate/preview must match what gets sent
                }}
                placeholder={t("bc.varHint")}
              />
            </div>
          ))}
          <div className="space-y-1.5">
            <Label>{t("bc.campaignName")}</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Pengingat kontrol Oktober" />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={estimate} disabled={!tpl || vars.some((v) => !v.trim())}>
              {t("bc.estimate")}
            </Button>
            <Button onClick={createAndSend} disabled={!est || est.recipients === 0} data-testid="bc-send">
              {t("bc.sendTo", { n: est?.recipients ?? 0 })}
            </Button>
          </div>
        </div>
        <div className="space-y-2 text-sm">
          {est ? (
            <>
              <div className="grid grid-cols-2 gap-2">
                <Stat label={t("bc.recipients")} value={String(est.recipients)} />
                <Stat label={t("bc.cost")} value={idr(est.total_idr)} />
                <Stat label={t("bc.rate", { cat: est.category })} value={idr(est.rate_idr)} />
                <Stat label={t("bc.thisMonth")} value={`${est.template_messages_this_month} / ${est.free_tier}`} />
              </div>
              {est.simulated > 0 && <p className="text-xs text-muted-foreground">{t("bc.simulatedNote", { n: est.simulated })}</p>}
              <div className="text-xs text-muted-foreground">
                {t("bc.to", { list: est.sample.join(", ") + (est.recipients > est.sample.length ? "…" : "") })}
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t("bc.preview")}</div>
                <div className="mt-1 rounded-lg bg-accent px-3.5 py-2.5 text-sm whitespace-pre-wrap">{est.preview}</div>
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">{t("bc.consentNote")}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted px-3 py-2.5">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-lg font-semibold">{value}</div>
    </div>
  );
}

function Campaign({ id }: { id: number }) {
  const t = useT();
  const { data: b } = useSWR<Broadcast>(`/broadcasts/${id}`, { refreshInterval: 5000 });
  if (!b) return null;
  const s = b.stats;
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {b.name} · <span className="font-normal">{b.status}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
          <Stat label={t("bc.recipients")} value={String(b.recipient_count)} />
          <Stat label={t("bc.sent")} value={String(s.sent)} />
          <Stat label={t("bc.delivered")} value={String(s.delivered)} />
          <Stat label={t("bc.read")} value={String(s.read)} />
          <Stat label={t("bc.failed")} value={String(s.failed)} />
          <Stat label={t("bc.cost")} value={idr(b.est_cost_idr)} />
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("bc.contact")}</TableHead>
              <TableHead>{t("bc.status")}</TableHead>
              <TableHead>{t("bc.tries")}</TableHead>
              <TableHead>{t("bc.sent")}</TableHead>
              <TableHead>{t("bc.read")}</TableHead>
              <TableHead>{t("bc.error")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {b.recipients?.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="text-xs">{r.contact_name}</TableCell>
                <TableCell className={cn("text-xs", r.status === "failed" && "text-destructive")}>{r.status}</TableCell>
                <TableCell className="text-xs">{r.attempts}</TableCell>
                <TableCell className="text-xs">{clock(r.sent_at)}</TableCell>
                <TableCell className="text-xs">{clock(r.read_at)}</TableCell>
                <TableCell className="max-w-xs truncate text-xs">{r.error}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function Broadcasts() {
  const t = useT();
  const params = useSearchParams();
  const router = useRouter();
  const selected = params.get("id") ? Number(params.get("id")) : null;
  const { data } = useSWR<Broadcast[]>("/broadcasts");
  return (
    <div className="h-full space-y-4 overflow-y-auto p-6">
      <Composer onCreated={(id) => router.push(`/broadcasts?id=${id}`)} />
      {selected && <Campaign key={selected} id={selected} />}
      <Card>
        <CardHeader>
          <CardTitle>{t("bc.campaigns")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("bc.name")}</TableHead>
                <TableHead>{t("bc.template")}</TableHead>
                <TableHead>{t("bc.status")}</TableHead>
                <TableHead>{t("bc.progress")}</TableHead>
                <TableHead>{t("bc.cost")}</TableHead>
                <TableHead>{t("bc.created")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.map((b) => (
                <TableRow key={b.id} className="cursor-pointer" onClick={() => router.push(`/broadcasts?id=${b.id}`)}>
                  <TableCell className="text-xs font-medium">{b.name}</TableCell>
                  <TableCell className="font-mono text-xs">{b.template?.name}</TableCell>
                  <TableCell className="text-xs">{b.status}</TableCell>
                  <TableCell className="text-xs">
                    {b.stats.sent} / {b.stats.delivered} / {b.stats.read} / {b.stats.failed}
                  </TableCell>
                  <TableCell className="text-xs">{idr(b.est_cost_idr)}</TableCell>
                  <TableCell className="text-xs">{clock(b.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Templates />
    </div>
  );
}

export default function BroadcastsPage() {
  return (
    <Suspense>
      <Broadcasts />
    </Suspense>
  );
}
