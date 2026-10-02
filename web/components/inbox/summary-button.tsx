"use client";

import { useState } from "react";
import { Sparkles, X } from "lucide-react";
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
      <Button size="sm" variant="ghost" onClick={run} disabled={busy} data-testid="summary-button">
        <Sparkles /> {busy ? "Summarising…" : "AI summary"}
      </Button>
      {summary && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-[#272b32]/30 p-16" onClick={() => setSummary(null)}>
          <div
            className="w-full max-w-lg rounded-lg bg-white p-6 shadow-[0_20px_25px_-5px_rgba(39,43,50,0.15)]"
            onClick={(e) => e.stopPropagation()}
            data-testid="summary-dialog"
          >
            <div className="mb-3 flex items-center gap-2">
              <h2 className="flex-1 text-[15px] font-semibold">Summary for takeover</h2>
              <button className="rounded p-1 text-muted-foreground hover:bg-muted" onClick={() => setSummary(null)} aria-label="Close">
                <X className="size-4" />
              </button>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{summary.summary}</p>
            <p className="mt-4 text-xs text-muted-foreground">
              AI-generated with {summary.model} ({idr(summary.cost_idr, 2)}). Check the thread before acting.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
