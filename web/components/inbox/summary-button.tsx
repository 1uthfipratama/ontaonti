"use client";

import { useState } from "react";
import { Loader2, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import { api, errorMessage } from "@/lib/api";
import { idr } from "@/lib/format";
import { useT } from "@/lib/i18n";

/** AI summary for staff taking over. Staff-facing only; never sent to the patient. */
export function SummaryButton({ conversationId }: { conversationId: number }) {
  const t = useT();
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<{ summary: string; model: string; cost_idr: number } | null>(null);

  async function run() {
    setBusy(true);
    try {
      setSummary(await api(`/conversations/${conversationId}/summary`, { method: "POST" }));
    } catch (e) {
      toast.error(errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={run}
        disabled={busy}
        title={t("thread.summary")}
        aria-label={t("thread.summary")}
        data-testid="summary-button"
        className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-50"
      >
        {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
      </button>
      {summary && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-16" onClick={() => setSummary(null)}>
          <div
            className="w-full max-w-lg rounded-lg bg-card p-6 shadow-[0_20px_25px_-5px_rgba(0,0,0,0.15)]"
            onClick={(e) => e.stopPropagation()}
            data-testid="summary-dialog"
          >
            <div className="mb-3 flex items-center gap-2">
              <h2 className="flex-1 text-[15px] font-semibold">{t("summary.title")}</h2>
              <button className="rounded p-1 text-muted-foreground hover:bg-muted" onClick={() => setSummary(null)} aria-label={t("common.close")}>
                <X className="size-4" />
              </button>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{summary.summary}</p>
            <p className="mt-4 text-xs text-muted-foreground">
              {t("summary.footer", { model: summary.model, cost: idr(summary.cost_idr, 2) })}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
