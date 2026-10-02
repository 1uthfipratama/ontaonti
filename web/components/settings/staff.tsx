"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, errorMessage } from "@/lib/api";
import { useStaff } from "@/lib/session";
import type { Staff } from "@/lib/types";

const ROLES = [
  { value: "agent", label: "agent (inbox, cases, replies)" },
  { value: "reviewer", label: "reviewer (read-only + audit)" },
  { value: "admin", label: "admin (everything)" },
];

export function StaffManager() {
  const me = useStaff();
  const { mutate } = useSWRConfig();
  const { data } = useSWR<Staff[]>("/staff");
  const [form, setForm] = useState({ email: "", name: "", role: "agent", password: "" });

  async function run(fn: () => Promise<unknown>, ok: string) {
    try {
      await fn();
      toast.success(ok);
      mutate("/staff");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  return (
    <Card>
      <CardContent className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
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
                    onChange={(e) => run(() => api(`/staff/${s.id}`, { method: "PATCH", json: { role: e.target.value } }), "Role updated")}
                    options={ROLES.map((r) => ({ value: r.value, label: r.value }))}
                  />
                </TableCell>
                <TableCell>
                  {s.id === me.id ? (
                    <span className="text-xs text-muted-foreground">you</span>
                  ) : (
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => run(() => api(`/staff/${s.id}`, { method: "PATCH", json: { is_active: !s.is_active } }), s.is_active ? "Deactivated" : "Activated")}
                    >
                      {s.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="grid gap-2 md:grid-cols-5">
          <Input placeholder="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <Input placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <NativeSelect value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} options={ROLES} />
          <Input
            type="password"
            placeholder="password (10+ chars)"
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
              }, "Staff member added")
            }
          >
            Add staff
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
