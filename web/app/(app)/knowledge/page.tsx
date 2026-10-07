"use client";

import { Suspense, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Check, FileText, Loader2, Trash2, Upload, X } from "lucide-react";

import { mediaSrc } from "@/components/message-media";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { day, timeAgo } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useCanAct, useStaff } from "@/lib/session";
import { cn } from "@/lib/utils";

type ArticleRow = {
  id: number;
  doc_id: string;
  title: string;
  published: boolean;
  updated_at: string;
  source_name: string;
  source_url: string | null;
};
type Report = { pages: number; sections: number; words: number; warnings: string[] };
type Article = ArticleRow & { body: string };
type Status = { state: string; error?: string; published_at: string | null; pending: boolean; open_gaps: number };
type Gap = { id: number; question: string; conversation_id: number | null; created_at: string };

function PublishBar({ status }: { status: Status }) {
  const t = useT();
  const { mutate } = useSWRConfig();
  const admin = useStaff().role === "admin";
  const busy = status.state === "queued" || status.state === "running";

  async function publish() {
    try {
      mutate("/kb/status", await api<Status>("/kb/publish", { method: "POST" }), { revalidate: false });
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  let text = status.published_at ? t("kb.upToDate", { date: day(status.published_at) }) : "";
  if (status.pending) text = t("kb.pending");
  if (busy) text = t("kb.updating");
  if (status.state === "error") text = t("kb.failed", { error: status.error ?? "" });
  return (
    <div className="flex items-center gap-3 text-sm">
      {busy && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
      <span className={cn("text-muted-foreground", status.state === "error" && "text-destructive")} data-testid="kb-status">
        {text}
      </span>
      {admin && (status.pending || status.state === "error") && !busy && (
        <Button size="sm" onClick={publish} data-testid="kb-publish">
          {t("kb.publish")}
        </Button>
      )}
    </div>
  );
}

function Editor({
  id,
  onDone,
  report,
  onDismissReport,
}: {
  id: number | "new";
  onDone: (id: number | null) => void;
  report?: Report | null;
  onDismissReport?: () => void;
}) {
  const t = useT();
  const { mutate } = useSWRConfig();
  const admin = useStaff().role === "admin";
  const { data } = useSWR<Article>(id === "new" ? null : `/kb/articles/${id}`);
  const [draft, setDraft] = useState<Partial<Article>>({});
  const a = { title: "", body: "", published: true, ...data, ...draft };
  const dirty = Object.keys(draft).length > 0;
  const refresh = () => mutate((k) => typeof k === "string" && k.startsWith("/kb"));

  async function save() {
    try {
      const json = { title: a.title, body: a.body, published: a.published };
      const saved =
        id === "new"
          ? await api<Article>("/kb/articles", { json })
          : await api<Article>(`/kb/articles/${id}`, { method: "PUT", json });
      setDraft({});
      refresh();
      onDone(saved.id);
      toast.success(t("common.saved"));
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  async function remove() {
    if (id === "new" || !confirm(t("kb.deleteConfirm", { title: a.title }))) return;
    try {
      await api(`/kb/articles/${id}`, { method: "DELETE" });
      refresh();
      onDone(null);
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  if (id !== "new" && !data) return <div className="p-6 text-sm text-muted-foreground">{t("common.loading")}</div>;
  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <div className="flex items-center gap-3 border-b border-border px-6 py-3">
        <Input
          value={a.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          placeholder={t("kb.titlePlaceholder")}
          disabled={!admin}
          className="h-9 flex-1 border-transparent px-0 text-[15px] font-semibold shadow-none focus-visible:border-transparent focus-visible:shadow-none"
          data-testid="kb-title"
        />
        {data?.source_url && (
          <a
            href={mediaSrc({ media_url: data.source_url }) ?? "#"}
            target="_blank"
            rel="noreferrer"
            title={data.source_name}
            className="inline-flex max-w-48 items-center gap-1 text-xs text-muted-foreground hover:text-primary"
          >
            <FileText className="size-3.5 shrink-0" />
            <span className="truncate">{data.source_name}</span>
          </a>
        )}
        {data && <span className="font-mono text-xs text-subtle-foreground">{data.doc_id}</span>}
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          {t("kb.visible")}
          <Switch
            checked={a.published}
            disabled={!admin}
            onCheckedChange={(v) => setDraft({ ...draft, published: v })}
          />
        </label>
      </div>
      {report && (
        <div className="flex items-start gap-3 border-b border-border bg-accent/60 px-6 py-2.5 text-sm" data-testid="kb-report">
          <div className="flex-1">
            <div>{t("kb.imported", { sections: report.sections, words: report.words.toLocaleString("id-ID") })}</div>
            {report.warnings.map((w) => (
              <div key={w} className="text-xs text-muted-foreground">
                {t(`kb.warn.${w}`) === `kb.warn.${w}` ? w : t(`kb.warn.${w}`)}
              </div>
            ))}
          </div>
          <button onClick={onDismissReport} aria-label={t("common.close")} className="rounded p-0.5 text-muted-foreground hover:bg-muted">
            <X className="size-4" />
          </button>
        </div>
      )}
      <Textarea
        value={a.body}
        onChange={(e) => setDraft({ ...draft, body: e.target.value })}
        disabled={!admin}
        className="min-h-0 flex-1 resize-none rounded-none border-0 px-6 py-4 leading-relaxed shadow-none focus-visible:shadow-none"
        data-testid="kb-body"
      />
      {admin && (
        <div className="flex items-center gap-2 border-t border-border px-6 py-3">
          <span className="flex-1 text-xs text-muted-foreground">{t("kb.hint")}</span>
          {id !== "new" && (
            <Button size="sm" variant="ghost" className="text-destructive" onClick={remove}>
              <Trash2 /> {t("common.delete")}
            </Button>
          )}
          <Button size="sm" onClick={save} disabled={!dirty || !a.title.trim()} data-testid="kb-save">
            {t("common.save")}
          </Button>
        </div>
      )}
    </div>
  );
}

function Articles() {
  const t = useT();
  const admin = useStaff().role === "admin";
  const { data } = useSWR<ArticleRow[]>("/kb/articles");
  const { mutate } = useSWRConfig();
  const [selected, setSelected] = useState<number | "new" | null>(null);
  const [report, setReport] = useState<{ id: number; report: Report } | null>(null);
  const [uploading, setUploading] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const current = selected ?? data?.[0]?.id ?? null;

  async function upload(file: File) {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await api<{ article: ArticleRow; report: Report }>("/kb/upload", { form });
      await mutate((k) => typeof k === "string" && k.startsWith("/kb"));
      setSelected(r.article.id);
      setReport({ id: r.article.id, report: r.report });
    } catch (e) {
      toast.error(errorMessage(e, t));
    } finally {
      setUploading(false);
    }
  }
  return (
    <div className="grid min-h-0 flex-1 grid-cols-[17rem_minmax(0,1fr)] grid-rows-[minmax(0,1fr)] xl:grid-cols-[20rem_minmax(0,1fr)]">
      <div className="overflow-y-auto border-r border-border bg-card p-2">
        {admin && (
          <button
            onClick={() => setSelected("new")}
            className={cn("block w-full rounded-md px-3 py-2 text-left text-sm font-medium text-primary hover:bg-muted", current === "new" && "bg-accent")}
          >
            + {t("kb.new")}
          </button>
        )}
        {admin && (
          <>
            <input
              ref={picker}
              type="file"
              hidden
              accept=".pdf,.docx,.txt,.md"
              data-testid="kb-upload-input"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) upload(f);
                e.target.value = "";
              }}
            />
            <button
              onClick={() => picker.current?.click()}
              disabled={uploading}
              title={t("kb.uploadHint")}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium text-primary hover:bg-muted disabled:opacity-60"
            >
              {uploading ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
              {uploading ? t("kb.reading") : t("kb.upload")}
            </button>
          </>
        )}
        {data?.map((a) => (
          <button
            key={a.id}
            onClick={() => setSelected(a.id)}
            data-testid="kb-item"
            className={cn("block w-full rounded-md px-3 py-2 text-left hover:bg-muted", current === a.id && "bg-accent hover:bg-accent")}
          >
            <div className={cn("truncate text-sm", a.published ? "font-medium" : "text-muted-foreground")}>{a.title}</div>
            <div className="text-xs text-muted-foreground">
              {a.doc_id}
              {!a.published && ` · ${t("kb.hidden")}`}
            </div>
          </button>
        ))}
      </div>
      {current !== null && (
        <Editor
          key={current}
          id={current}
          onDone={(id) => setSelected(id)}
          report={report?.id === current ? report.report : null}
          onDismissReport={() => setReport(null)}
        />
      )}
    </div>
  );
}

function Gaps() {
  const t = useT();
  const { mutate } = useSWRConfig();
  const canAct = useCanAct();
  const { data } = useSWR<Gap[]>("/kb/gaps");

  async function mark(id: number, status: "done" | "ignored") {
    try {
      await api(`/kb/gaps/${id}`, { json: { status } });
      mutate((k) => typeof k === "string" && k.startsWith("/kb"));
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl">
        <p className="mb-4 text-sm text-muted-foreground">{t("kb.gapsIntro")}</p>
        {data?.length === 0 && <p className="text-sm text-muted-foreground">{t("kb.noGaps")}</p>}
        <div className="divide-y divide-divider rounded-lg bg-card">
          {data?.map((g) => (
            <div key={g.id} className="flex items-start gap-4 px-5 py-3.5" data-testid="kb-gap">
              <div className="min-w-0 flex-1">
                <p className="text-sm">{g.question}</p>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {timeAgo(g.created_at, t)}
                  {g.conversation_id && (
                    <>
                      {" · "}
                      <Link href={`/inbox?c=${g.conversation_id}`} className="text-primary hover:underline">
                        {t("cases.openConversation")}
                      </Link>
                    </>
                  )}
                </div>
              </div>
              {canAct && (
                <div className="flex shrink-0 gap-1">
                  <Button size="sm" variant="ghost" onClick={() => mark(g.id, "ignored")}>
                    {t("kb.ignore")}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => mark(g.id, "done")}>
                    <Check /> {t("kb.done")}
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Knowledge() {
  const t = useT();
  const router = useRouter();
  const tab = useSearchParams().get("tab") === "gaps" ? "gaps" : "articles";
  const { data: status } = useSWR<Status>("/kb/status", {
    refreshInterval: (s) => (s && (s.state === "queued" || s.state === "running") ? 2000 : 30000),
  });
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-border bg-card px-4">
        {(["articles", "gaps"] as const).map((k) => (
          <button
            key={k}
            onClick={() => router.replace(k === "gaps" ? "/knowledge?tab=gaps" : "/knowledge")}
            data-testid={`kb-tab-${k}`}
            className={cn(
              "-mb-px border-b-2 px-3 py-2.5 text-sm",
              tab === k ? "border-primary font-semibold" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {k === "articles" ? t("kb.articles") : t("kb.gaps")}
            {k === "gaps" && (status?.open_gaps ?? 0) > 0 && (
              <span className="ml-1.5 rounded-full bg-secondary px-1.5 text-xs font-semibold">{status?.open_gaps}</span>
            )}
          </button>
        ))}
        <span className="flex-1" />
        {status && <PublishBar status={status} />}
      </div>
      {tab === "articles" ? <Articles /> : <Gaps />}
    </div>
  );
}

export default function KnowledgePage() {
  return (
    <Suspense>
      <Knowledge />
    </Suspense>
  );
}
