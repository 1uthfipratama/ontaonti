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

import { ThemeToggle } from "@/components/theme-toggle";
import { api, fetcher } from "@/lib/api";
import { useStaff } from "@/lib/session";
import { cn } from "@/lib/utils";

type Summary = { open_cases: number; emergency: number; high: number; needs_human: number };
type NavItem = {
  href: string;
  label: string;
  icon: typeof Inbox;
  badge?: boolean;
  adminOnly?: boolean;
  actOnly?: boolean;
  auditOnly?: boolean;
};

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Conversations",
    items: [
      { href: "/inbox", label: "Inbox", icon: Inbox },
      { href: "/cases", label: "Cases", icon: LifeBuoy, badge: true },
      { href: "/contacts", label: "Contacts", icon: Users },
      { href: "/simulator", label: "Simulator", icon: FlaskConical, actOnly: true },
    ],
  },
  {
    group: "Outreach",
    items: [{ href: "/broadcasts", label: "Broadcasts", icon: Megaphone, adminOnly: true }],
  },
  {
    group: "Reports",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
      { href: "/audit", label: "Audit log", icon: ScrollText, auditOnly: true },
    ],
  },
  {
    group: "Admin",
    items: [{ href: "/settings", label: "Settings", icon: Settings, adminOnly: true }],
  },
];

function initials(name: string): string {
  return name
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const staff = useStaff();
  const path = usePathname();
  const router = useRouter();
  const { data: summary } = useSWR<Summary>("/notifications/summary", fetcher, {
    shouldRetryOnError: false,
  });

  const allowed = (n: NavItem) =>
    (!n.adminOnly || staff.role === "admin") &&
    (!n.actOnly || staff.role !== "reviewer") &&
    (!n.auditOnly || staff.role !== "agent");
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter(allowed) })).filter((g) => g.items.length);
  const current = NAV.flatMap((g) => g.items).find((n) => path.startsWith(n.href));

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  return (
    <div className="flex h-screen">
      <aside className="flex w-16 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:w-60">
        <div className="flex h-14 items-center justify-center gap-2.5 lg:justify-start lg:px-5">
          <div className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
            OE
          </div>
          <div className="hidden leading-tight lg:block">
            <div className="text-sm font-semibold">Onti Erlani</div>
            <div className="text-[11px] text-muted-foreground">TB companion hub</div>
          </div>
        </div>
        <nav className="flex-1 space-y-5 overflow-y-auto px-2 py-3 lg:px-3">
          {groups.map((g) => (
            <div key={g.group}>
              <div className="hidden px-2 pb-1.5 text-[11px] font-semibold text-subtle-foreground lg:block">{g.group}</div>
              <div className="space-y-0.5">
                {g.items.map((n) => {
                  const active = path.startsWith(n.href);
                  const count = n.badge ? (summary?.open_cases ?? 0) : 0;
                  return (
                    <Link
                      key={n.href}
                      href={n.href}
                      title={n.label}
                      className={cn(
                        "relative flex h-9 items-center justify-center gap-2.5 rounded-md px-2.5 text-sm lg:justify-start text-sidebar-foreground transition-colors hover:bg-muted",
                        active && "bg-sidebar-accent font-semibold text-sidebar-accent-foreground hover:bg-sidebar-accent",
                      )}
                    >
                      <n.icon className={cn("size-[18px]", active ? "text-primary" : "text-muted-foreground")} />
                      <span className="hidden flex-1 lg:inline">{n.label}</span>
                      {count > 0 && (
                        <span
                          data-testid="cases-badge"
                          className={cn(
                            "absolute -top-1 right-0 min-w-5 rounded-full px-1.5 text-center text-[11px] font-semibold leading-5 text-white lg:static",
                            (summary?.emergency ?? 0) > 0 ? "bg-destructive" : "bg-primary",
                          )}
                        >
                          {count}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        <div className="flex flex-col items-center gap-2.5 border-t border-sidebar-border px-2 py-3 lg:flex-row lg:px-4">
          <div className="flex size-8 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
            {initials(staff.name || staff.email)}
          </div>
          <div className="hidden min-w-0 flex-1 leading-tight lg:block">
            <div className="truncate text-sm font-medium">{staff.name || staff.email}</div>
            <div className="text-xs capitalize text-muted-foreground">{staff.role}</div>
          </div>
          <button
            onClick={logout}
            title="Sign out"
            aria-label="Sign out"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-card px-6">
          <h1 className="text-base font-semibold" data-testid="page-title">
            {current?.label ?? ""}
          </h1>
          <ThemeToggle className="ml-auto" />
        </header>
        <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
