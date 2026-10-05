"use client";

import { ThemeProvider } from "next-themes";
import { SWRConfig } from "swr";

import { Toaster } from "@/components/ui/sonner";
import { fetcher } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <SWRConfig value={{ fetcher, revalidateOnFocus: true }}>
        {children}
        <Toaster richColors position="top-right" />
      </SWRConfig>
    </ThemeProvider>
  );
}
