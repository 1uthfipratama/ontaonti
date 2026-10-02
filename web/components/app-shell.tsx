"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import useSWR from "swr";
import {
  BarChart3,
  FlaskConical,
  Inbox,
  LifeBuoy,
  LogOut,
  Megaphone,
  ScrollText,
  Settings,
  Users,
} from "lucide-react";

import { api, fetcher } from "@/lib/api";
import { useStaff } from "@/lib/session";
import { cn } from "@/lib/utils";

type Summary = { open_cases: number; emergency: number; high: number; needs_human: number };

const NAV = [
  { href: "/inbox", label: "Inbox", icon: Inbox },
  { href: "/cases", label: "Cases", icon: LifeBuoy, badge: true },
  { href: "/contacts", label: "Contacts", icon: Users },
  { href: "/simulator", label: "Simulator", icon: FlaskConical, actOnly: true },
  { href: "/broadcasts", label: "Broadcasts", icon: Megaphone, adminOnly: true },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings, adminOnly: true },
  { href: "/audit", label: "Audit log", icon: ScrollText, auditOnly: true },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const staff = useStaff();
  const path = usePathname();
  const router = useRouter();
  const { data: summary } = useSWR<Summary>("/notifications/summary", fetcher, {
    shouldRetryOnError: false,
  });

  const visible = NAV.filter(
    (n) =>
      (!n.adminOnly || staff.role === "admin") &&
      (!n.actOnly || staff.role !== "reviewer") &&
      (!n.auditOnly || staff.role !== "agent"),
  );

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  return (
    <div className="flex h-screen flex-col">
      <div
        role="status"
        className="bg-amber-400 px-4 py-1 text-center text-xs font-semibold text-amber-950"
        data-testid="prototype-banner"
      >
        Prototype — test data only. Not for real patient data.
      </div>
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-52 shrink-0 flex-col border-r bg-muted/30">
          <div className="px-4 py-4">
            <div className="text-sm font-bold">Onti Erlani Hub</div>
            <div className="text-[11px] text-muted-foreground">TB companion · inbox</div>
          </div>
          <nav className="flex-1 space-y-0.5 px-2">
            {visible.map((n) => {
              const active = path.startsWith(n.href);
              const count = n.badge ? (summary?.open_cases ?? 0) : 0;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted",
                    active && "bg-muted font-medium",
                  )}
                >
                  <n.icon className="size-4" />
                  <span className="flex-1">{n.label}</span>
                  {count > 0 && (
                    <span
                      data-testid="cases-badge"
                      className={cn(
                        "rounded-full px-1.5 text-[11px] font-bold text-white",
                        (summary?.emergency ?? 0) > 0 ? "bg-red-600" : "bg-orange-500",
                      )}
                    >
                      {count}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
          <div className="border-t px-3 py-3 text-xs">
            <div className="truncate font-medium">{staff.name || staff.email}</div>
            <div className="text-muted-foreground">{staff.role}</div>
            <button
              onClick={logout}
              className="mt-2 inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
            >
              <LogOut className="size-3" /> Sign out
            </button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
