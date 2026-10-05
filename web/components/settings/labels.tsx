"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { LabelRef } from "@/lib/types";

export function LabelManager() {
  const t = useT();
  const { mutate } = useSWRConfig();
  const { data } = useSWR<LabelRef[]>("/labels");
  const [name, setName] = useState("");
  const refresh = () => mutate((k) => typeof k === "string" && (k === "/labels" || k.startsWith("/conversations")));

  async function add() {
    try {
      await api("/labels", { json: { name } });
      setName("");
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  async function remove(l: LabelRef) {
    if (!confirm(t("labels.deleteConfirm", { name: l.name }))) return;
    try {
      await api(`/labels/${l.id}`, { method: "DELETE" });
      refresh();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <div className="space-y-4 rounded-lg bg-card p-5">
      <form
        className="flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) add();
        }}
      >
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("labels.placeholder")} />
        <Button type="submit" variant="outline" disabled={!name.trim()}>
          {t("common.add")}
        </Button>
      </form>
      {data?.length === 0 && <p className="text-sm text-muted-foreground">{t("labels.empty")}</p>}
      <div className="flex flex-wrap gap-2">
        {data?.map((l) => (
          <span key={l.id} className="inline-flex items-center gap-1 rounded-md bg-secondary py-1 pr-1 pl-2.5 text-sm">
            {l.name}
            <button
              onClick={() => remove(l)}
              aria-label={`${t("common.delete")} ${l.name}`}
              className="rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
