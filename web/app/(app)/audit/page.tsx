"use client";

import { useState } from "react";
import useSWR from "swr";

import { NativeSelect } from "@/components/native-select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { clock } from "@/lib/format";
import type { AuditRow } from "@/lib/types";

const ACTIONS = ["", "auth", "conversation", "case", "contact", "settings", "broadcast", "staff", "simulator"];

export default function AuditPage() {
  const [action, setAction] = useState("");
  const { data, error } = useSWR<AuditRow[]>(`/audit?limit=300${action ? `&action=${action}` : ""}`);
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="text-lg font-semibold">Audit log</h1>
        <NativeSelect
          value={action}
          onChange={(e) => setAction(e.target.value)}
          options={ACTIONS.map((a) => ({ value: a, label: a || "All actions" }))}
        />
      </div>
      {error && <p className="text-sm text-red-600">{error.message}</p>}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>Who</TableHead>
            <TableHead>Action</TableHead>
            <TableHead>Target</TableHead>
            <TableHead>Details</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data?.map((r) => (
            <TableRow key={r.id}>
              <TableCell className="whitespace-nowrap text-xs">{clock(r.created_at)}</TableCell>
              <TableCell className="text-xs">{r.actor_email}</TableCell>
              <TableCell className="font-mono text-xs">{r.action}</TableCell>
              <TableCell className="text-xs">
                {r.entity_type} {r.entity_id}
              </TableCell>
              <TableCell className="max-w-md truncate font-mono text-[11px] text-muted-foreground">
                {Object.keys(r.details ?? {}).length ? JSON.stringify(r.details) : ""}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
