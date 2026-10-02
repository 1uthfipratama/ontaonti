"use client";

import { SWRConfig } from "swr";

import { Toaster } from "@/components/ui/sonner";
import { fetcher } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: true }}>
      {children}
      <Toaster richColors position="top-right" />
    </SWRConfig>
  );
}
