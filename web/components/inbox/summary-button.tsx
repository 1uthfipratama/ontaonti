"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { idr } from "@/lib/format";

/** AI summary for an agent taking over. Staff-facing only; never sent to the user. */
export function SummaryButton({ conversationId }: { conversationId: number }) {
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<{ summary: string; model: string; cost_idr: number } | null>(null);

  async function run() {
    setBusy(true);
    try {
      setSummary(await api(`/conversations/${conversationId}/summary`, { method: "POST" }));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button size="sm" variant="outline" onClick={run} disabled={busy} data-testid="summary-button">
        <Sparkles /> {busy ? "Summarising…" : "AI summary"}
      </Button>
      {summary && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 p-10" onClick={() => setSummary(null)}>
          <div
            className="max-w-lg rounded-xl border bg-background p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
            data-testid="summary-dialog"
          >
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="size-4" />
              <h2 className="font-semibold">AI summary for takeover</h2>
            </div>
            <p className="whitespace-pre-wrap text-sm">{summary.summary}</p>
            <p className="mt-3 text-[11px] text-muted-foreground">
              {summary.model} · {idr(summary.cost_idr, 2)} · AI-generated, check the thread before acting.
            </p>
            <div className="mt-3 text-right">
              <Button size="sm" onClick={() => setSummary(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
