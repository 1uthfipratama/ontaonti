"use client";

import { ChannelStatus } from "@/components/settings/channels";
import { SettingsEditor } from "@/components/settings/editor";
import { StaffManager } from "@/components/settings/staff";

export default function SettingsPage() {
  return (
    <div className="h-full space-y-8 overflow-y-auto p-6">
      <section>
        <h1 className="mb-3 text-lg font-semibold">Channels</h1>
        <ChannelStatus />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Bot, safety and cost settings</h2>
        <SettingsEditor />
      </section>
      <section>
        <h2 className="mb-3 text-lg font-semibold">Staff</h2>
        <StaffManager />
      </section>
    </div>
  );
}
