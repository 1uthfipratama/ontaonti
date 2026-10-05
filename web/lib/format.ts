import type { T } from "@/lib/i18n";

export function timeAgo(iso: string | null | undefined, t: T): string {
  if (!iso) return "";
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return t("time.justNow");
  if (s < 3600) return t("time.minutes", { n: Math.round(s / 60) });
  if (s < 86400) return t("time.hours", { n: Math.round(s / 3600) });
  return t("time.days", { n: Math.round(s / 86400) });
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function day(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

export function idr(n: number | null | undefined, digits = 0): string {
  return `Rp ${(n ?? 0).toLocaleString("id-ID", { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
}

export function windowLeft(iso: string | null | undefined, t: T): string {
  if (!iso) return t("time.windowClosed");
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return t("time.windowClosed");
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return t("time.windowLeft", { h, m });
}
