"use client";

import { createContext, useContext, useEffect, useRef } from "react";
import useSWR, { useSWRConfig } from "swr";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { API_URL, fetcher } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { Staff } from "@/lib/types";

const SessionContext = createContext<Staff | null>(null);

export function useStaff(): Staff {
  const s = useContext(SessionContext);
  if (!s) throw new Error("useStaff outside SessionProvider");
  return s;
}

/** Re-read /auth/me (after turning 2FA on or off). */
export function useStaffMutate() {
  const { mutate } = useSWRConfig();
  return () => mutate("/auth/me");
}

export function useCanAct(): boolean {
  const s = useStaff();
  return s.role === "admin" || s.role === "agent";
}

/** Loads /auth/me; redirects to /login when signed out. */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data, error, isLoading } = useSWR<Staff>("/auth/me", fetcher, {
    shouldRetryOnError: false,
    revalidateOnFocus: false,
  });
  useEffect(() => {
    if (error) router.replace("/login");
  }, [error, router]);
  if (isLoading || !data) {
    return <Loading />;
  }
  return (
    <SessionContext.Provider value={data}>
      <LiveEvents />
      {children}
    </SessionContext.Provider>
  );
}

// SSE event type -> SWR key prefixes to refetch.
const REFRESH: Record<string, string[]> = {
  "message.created": ["/conversations", "/simulator", "/contacts"],
  "message.updated": ["/conversations", "/simulator"],
  "kb.status": ["/kb"],
  "kb.gap": ["/kb"],
  "conversation.updated": ["/conversations", "/simulator", "/notifications"],
  "conversation.needs_human": ["/conversations", "/notifications"],
  "contact.created": ["/contacts"],
  "contact.updated": ["/contacts", "/conversations"],
  "case.created": ["/cases", "/notifications", "/conversations", "/dashboard"],
  "case.updated": ["/cases", "/notifications", "/conversations", "/dashboard"],
  "broadcast.updated": ["/broadcasts", "/dashboard"],
  "budget.alert": ["/dashboard", "/notifications"],
};

function Loading() {
  const t = useT();
  return <div className="p-8 text-sm text-muted-foreground">{t("common.loading")}</div>;
}

function LiveEvents() {
  const t = useT();
  const { mutate } = useSWRConfig();
  const seen = useRef(false);
  useEffect(() => {
    const es = new EventSource(`${API_URL}/events`, { withCredentials: true });
    const handler = (ev: MessageEvent) => {
      const prefixes = REFRESH[ev.type] ?? [];
      mutate((key) => typeof key === "string" && prefixes.some((p) => key.startsWith(p)));
      if (ev.type === "case.created") {
        try {
          const data = JSON.parse(ev.data);
          toast.error(`${t("nav.cases")}: ${t(`sev.${data.severity}`)}`, {
            description: data.contact_name ?? "",
            duration: 10000,
          });
        } catch {
          /* ignore */
        }
      }
      if (ev.type === "budget.alert") {
        toast.warning(`${t("dash.aiSpend")}: ${t("dash.warn")}`);
      }
    };
    for (const type of Object.keys(REFRESH)) es.addEventListener(type, handler as EventListener);
    es.addEventListener("hello", () => {
      if (seen.current) mutate(() => true); // reconnected: refresh everything
      seen.current = true;
    });
    return () => es.close();
  }, [mutate, t]);
  return null;
}
