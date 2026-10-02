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
  const { mutate } = useSWRConfig();
  const { data } = useSWR<Template[]>("/templates");
  const [form, setForm] = useState({ name: "", language: "id", category: "UTILITY", body_text: "" });

  async function sync() {
    try {
      const r = await api<{ synced: number }>("/templates/sync", { method: "POST" });
      toast.success(`Synced ${r.synced} template(s) from WhatsApp`);
      mutate("/templates");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }
  async function register() {
    try {
      await api("/templates", { json: form });
      toast.success("Template registered");
      setForm({ ...form, name: "", body_text: "" });
      mutate("/templates");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
      <Card>
        <CardHeader className="flex flex-row items-center">
          <CardTitle className="flex-1">Templates</CardTitle>
          <Button size="sm" variant="outline" onClick={sync}>
            Sync from WhatsApp
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Lang</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Body</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="font-mono text-xs">{t.name}</TableCell>
                  <TableCell className="text-xs">{t.language}</TableCell>
                  <TableCell className="text-xs">{t.category}</TableCell>
                  <TableCell className="text-xs">{t.status}</TableCell>
                  <TableCell className="max-w-sm truncate text-xs">{t.body_text}</TableCell>
                </TableRow>
              ))}
              {data?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-xs text-muted-foreground">
                    No templates yet. Sync from WhatsApp (needs WA_BUSINESS_ACCOUNT_ID) or register one.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Register manually</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-[11px] text-muted-foreground">
            The template must already be approved in WhatsApp Manager with the same name and language.
          </p>
          <Input placeholder="name (lowercase_with_underscores)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="flex gap-2">
            <Input className="w-24" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
            <NativeSelect
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
              options={["UTILITY", "MARKETING", "AUTHENTICATION"].map((c) => ({ value: c, label: c }))}
            />
          </div>
          <Textarea placeholder="Body with {{1}}, {{2}}…" value={form.body_text} onChange={(e) => setForm({ ...form, body_text: e.target.value })} />
          <Button size="sm" onClick={register} disabled={!form.name || !form.body_text}>
            Register
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function Composer({ onCreated }: { onCreated: (id: number) => void }) {
  const { data: templates } = useSWR<Template[]>("/templates");
  const usable = templates?.filter((t) => ["APPROVED", "MANUAL"].includes(t.status)) ?? [];
  const [templateId, setTemplateId] = useState("");
  const [name, setName] = useState("");
  const [vars, setVars] = useState<string[]>([]);
  const [est, setEst] = useState<Estimate | null>(null);
  const t = usable.find((x) => String(x.id) === templateId);

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
      toast.error(errorMessage(e));
    }
  }
  async function createAndSend() {
    if (!est) return;
    if (!confirm(`Send "${t?.name}" to ${est.recipients} contact(s)? Estimated cost ${idr(est.total_idr)}.`)) return;
    try {
      const bc = await api<Broadcast>("/broadcasts", { json: { template_id: Number(templateId), variables: vars, name } });
      await api(`/broadcasts/${bc.id}/send`, { method: "POST" });
      toast.success("Broadcast queued");
      onCreated(bc.id);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>New broadcast</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>Template</Label>
            <NativeSelect
              data-testid="bc-template"
              className="w-full"
              value={templateId}
              onChange={(e) => chooseTemplate(e.target.value)}
              options={[{ value: "", label: "Choose an approved template…" }, ...usable.map((x) => ({ value: String(x.id), label: `${x.name} (${x.language}, ${x.category})` }))]}
            />
          </div>
          {t && <p className="rounded-lg bg-muted px-3 py-2 text-sm whitespace-pre-wrap">{t.body_text}</p>}
          {vars.map((v, i) => (
            <div key={i} className="space-y-1">
              <Label className="text-xs">{`{{${i + 1}}}`}</Label>
              <Input
                value={v}
                onChange={(e) => {
                  setVars(vars.map((x, j) => (j === i ? e.target.value : x)));
                  setEst(null); // estimate/preview must match what gets sent
                }}
                placeholder="text, or {{name}} for the contact's name"
              />
            </div>
          ))}
          <div className="space-y-1.5">
            <Label>Campaign name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Pengingat kontrol Oktober" />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={estimate} disabled={!t || vars.some((v) => !v.trim())}>
              Estimate cost
            </Button>
            <Button onClick={createAndSend} disabled={!est || est.recipients === 0} data-testid="bc-send">
              Send to {est?.recipients ?? 0}
            </Button>
          </div>
        </div>
        <div className="space-y-2 text-sm">
          {est ? (
            <>
              <div className="grid grid-cols-2 gap-2">
                <Stat label="Recipients (consented)" value={String(est.recipients)} />
                <Stat label="Estimated cost" value={idr(est.total_idr)} />
                <Stat label={`Rate (${est.category})`} value={idr(est.rate_idr)} />
                <Stat label="Template msgs this month" value={`${est.template_messages_this_month} / ${est.free_tier}`} />
              </div>
              {est.simulated > 0 && (
                <p className="text-xs text-muted-foreground">{est.simulated} simulated contact(s) get it in the simulator only.</p>
              )}
              <div className="text-xs text-muted-foreground">To: {est.sample.join(", ")}{est.recipients > est.sample.length ? "…" : ""}</div>
              <div>
                <div className="text-xs text-muted-foreground">Preview (first recipient)</div>
                <div className="mt-1 rounded-lg bg-accent px-3.5 py-2.5 text-sm whitespace-pre-wrap">{est.preview}</div>
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              Only contacts who gave broadcast consent (LANGGANAN or staff-recorded) and haven&apos;t sent STOP are included.
              Estimate shows the count, the cost from Settings → WhatsApp pricing, and a preview.
            </p>
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
          <Stat label="Recipients" value={String(b.recipient_count)} />
          <Stat label="Sent" value={String(s.sent)} />
          <Stat label="Delivered" value={String(s.delivered)} />
          <Stat label="Read" value={String(s.read)} />
          <Stat label="Failed" value={String(s.failed)} />
          <Stat label="Est. cost" value={idr(b.est_cost_idr)} />
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Contact</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Tries</TableHead>
              <TableHead>Sent</TableHead>
              <TableHead>Read</TableHead>
              <TableHead>Error</TableHead>
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
          <CardTitle>Campaigns</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Template</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Sent / delivered / read / failed</TableHead>
                <TableHead>Est. cost</TableHead>
                <TableHead>Created</TableHead>
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
