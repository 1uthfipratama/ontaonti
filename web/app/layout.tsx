import type { Metadata } from "next";
import { DM_Mono, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

import { Providers } from "@/components/providers";

// UI text: Plus Jakarta Sans. Fixed-width bits (IDs, URLs, prompts): DM Mono,
// a geometric monospace that pairs with Jakarta's shapes.
const jakarta = Plus_Jakarta_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
});

const dmMono = DM_Mono({
  variable: "--font-dm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Onti Erlani Hub",
  description: "Omnichannel inbox and TB companion chatbot",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // next-themes sets the "dark" class on <html> before React hydrates.
    <html
      lang="en"
      className={`${jakarta.variable} ${dmMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
