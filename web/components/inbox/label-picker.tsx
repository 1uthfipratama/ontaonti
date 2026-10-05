"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { Check, Tag } from "lucide-react";
import { toast } from "sonner";

import { Popover } from "@/components/popover";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Conversation, LabelRef } from "@/lib/types";

/** Tag icon in the thread header: tick labels on/off, or type a new one. */
export function LabelPicker({ conv, disabled }: { conv: Conversation; disabled?: boolean }) {
  const t = useT();
  const { mutate } = useSWRConfig();
  const { data: labels } = useSWR<LabelRef[]>("/labels");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const on = new Set(conv.labels.map((l) => l.id));
  const refresh = () => mutate((k) => typeof k === "string" && (k.startsWith("/conversations") || k === "/labels"));

  async function toggle(id: number) {
    try {
      if (on.has(id)) await api(`/conversations/${conv.id}/labels/${id}`, { method: "DELETE" });
      else await api(`/conversations/${conv.id}/labels`, { json: { label_id: id } });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  async function create() {
    if (!name.trim()) return;
    try {
      const lb = await api<LabelRef>("/labels", { json: { name } });
      await api(`/conversations/${conv.id}/labels`, { json: { label_id: lb.id } });
      setName("");
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        title={t("thread.labels")}
        aria-label={t("thread.labels")}
        data-testid="label-button"
        className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-50"
      >
        <Tag className="size-4" />
      </button>
      <Popover open={open} onClose={() => setOpen(false)} className="right-0 mt-1">
        <div className="max-h-60 overflow-y-auto">
          {labels?.map((l) => (
            <button
              key={l.id}
              onClick={() => toggle(l.id)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
            >
              <Check className={on.has(l.id) ? "size-4 text-primary" : "size-4 opacity-0"} />
              {l.name}
            </button>
          ))}
        </div>
        <form
          className="mt-1 border-t border-divider pt-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            create();
          }}
        >
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("thread.addLabel")}
            className="h-8"
            data-testid="label-input"
          />
        </form>
      </Popover>
    </div>
  );
}
