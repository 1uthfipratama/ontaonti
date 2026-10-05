"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { SavedReply } from "@/lib/types";
import { cn } from "@/lib/utils";

const EMPTY = { shortcut: "", title: "", body: "" };

/** List on the left, one editor on the right. "New" is just an empty editor. */
export function SavedReplies() {
  const t = useT();
  const { mutate } = useSWRConfig();
  const { data } = useSWR<SavedReply[]>("/saved-replies");
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY);

  function open(r: SavedReply | null) {
    setEditing(r?.id ?? null);
    setForm(r ? { shortcut: r.shortcut, title: r.title, body: r.body } : EMPTY);
  }

  async function save() {
    try {
      const r = editing
        ? await api<SavedReply>(`/saved-replies/${editing}`, { method: "PUT", json: form })
        : await api<SavedReply>("/saved-replies", { json: form });
      toast.success(t("common.saved"));
      mutate("/saved-replies");
      open(r);
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  async function remove() {
    if (!editing) return;
    try {
      await api(`/saved-replies/${editing}`, { method: "DELETE" });
      mutate("/saved-replies");
      open(null);
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <div className="grid gap-4 rounded-lg bg-card p-5 md:grid-cols-[16rem_1fr]">
      <div className="space-y-1">
        <button
          onClick={() => open(null)}
          className={cn(
            "block w-full rounded-md px-3 py-2 text-left text-sm font-medium text-primary hover:bg-muted",
            editing === null && "bg-accent",
          )}
        >
          + {t("replies.add")}
        </button>
        {data?.length === 0 && <p className="px-3 py-2 text-sm text-muted-foreground">{t("replies.empty")}</p>}
        {data?.map((r) => (
          <button
            key={r.id}
            onClick={() => open(r)}
            data-testid="saved-reply-item"
            className={cn("block w-full rounded-md px-3 py-2 text-left hover:bg-muted", editing === r.id && "bg-accent hover:bg-accent")}
          >
            <span className="font-mono text-xs text-primary">/{r.shortcut}</span>
            <div className="truncate text-sm">{r.title}</div>
          </button>
        ))}
      </div>
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-[12rem_1fr]">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="sr-shortcut">
              {t("replies.shortcut")}
            </label>
            <Input
              id="sr-shortcut"
              value={form.shortcut}
              onChange={(e) => setForm({ ...form, shortcut: e.target.value })}
              placeholder="jadwal"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="sr-title">
              {t("replies.title")}
            </label>
            <Input id="sr-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground" htmlFor="sr-body">
            {t("replies.body")}
          </label>
          <Textarea
            id="sr-body"
            className="min-h-36"
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
          />
        </div>
        <p className="text-xs text-muted-foreground">{t("replies.hint")}</p>
        <div className="flex gap-2">
          <Button size="sm" onClick={save} disabled={!form.shortcut.trim() || !form.title.trim() || !form.body.trim()} data-testid="saved-reply-save">
            {t("common.save")}
          </Button>
          {editing && (
            <Button size="sm" variant="ghost" onClick={remove} className="text-destructive">
              <Trash2 /> {t("common.delete")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
