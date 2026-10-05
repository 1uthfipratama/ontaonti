"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useStaff } from "@/lib/session";
import type { Staff } from "@/lib/types";

const ROLES = ["agent", "reviewer", "admin"] as const;

export function StaffManager() {
  const t = useT();
  const me = useStaff();
  const { mutate } = useSWRConfig();
  const { data } = useSWR<Staff[]>("/staff");
  const [form, setForm] = useState({ email: "", name: "", role: "agent", password: "" });
  const roleOptions = ROLES.map((r) => ({ value: r, label: t(`role.${r}`) }));

  async function run(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      toast.success(ok);
      mutate("/staff");
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <div className="space-y-4 rounded-lg bg-card p-5">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("staff.email")}</TableHead>
            <TableHead>{t("staff.name")}</TableHead>
            <TableHead>{t("staff.role")}</TableHead>
            <TableHead>{t("staff.twofa")}</TableHead>
            <TableHead>{t("staff.status")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data?.map((s) => (
            <TableRow key={s.id}>
              <TableCell className="text-xs">{s.email}</TableCell>
              <TableCell className="text-xs">{s.name}</TableCell>
              <TableCell>
                <NativeSelect
                  value={s.role}
                  disabled={s.id === me.id}
                  onChange={(e) =>
                    run(() => api(`/staff/${s.id}`, { method: "PATCH", json: { role: e.target.value } }), t("staff.roleUpdated"))
                  }
                  options={roleOptions}
                />
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {s.totp_enabled ? t("common.on") : t("common.off")}
                {s.totp_enabled && s.id !== me.id && (
                  <button
                    className="ml-2 font-medium text-primary hover:underline"
                    onClick={() =>
                      confirm(t("staff.reset2faConfirm", { name: s.name || s.email })) &&
                      run(() => api(`/staff/${s.id}`, { method: "PATCH", json: { reset_2fa: true } }), t("common.saved"))
                    }
                  >
                    {t("staff.reset2fa")}
                  </button>
                )}
              </TableCell>
              <TableCell>
                {s.id === me.id ? (
                  <span className="text-xs text-muted-foreground">{t("common.you")}</span>
                ) : (
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() =>
                      run(
                        () => api(`/staff/${s.id}`, { method: "PATCH", json: { is_active: !s.is_active } }),
                        t("common.saved"),
                      )
                    }
                  >
                    {s.is_active ? t("staff.deactivate") : t("staff.activate")}
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="grid gap-2 border-t border-divider pt-4 md:grid-cols-5">
        <Input placeholder={t("staff.email")} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Input placeholder={t("staff.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <NativeSelect value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} options={roleOptions} />
        <Input
          type="password"
          placeholder={t("staff.password")}
          autoComplete="new-password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <Button
          variant="outline"
          disabled={!form.email || form.password.length < 10}
          onClick={() =>
            run(async () => {
              await api("/staff", { json: form });
              setForm({ email: "", name: "", role: "agent", password: "" });
            }, t("staff.added"))
          }
        >
          {t("staff.add")}
        </Button>
      </div>
    </div>
  );
}
