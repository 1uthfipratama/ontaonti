"use client";

import { ChannelStatus } from "@/components/settings/channels";
import { SettingsEditor } from "@/components/settings/editor";
import { StaffManager } from "@/components/settings/staff";

export default function SettingsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 p-6">
        <section>
          <h2 className="mb-3 text-sm font-semibold">Channels</h2>
          <ChannelStatus />
        </section>
        <section>
          <h2 className="mb-3 text-sm font-semibold">Bot, safety and costs</h2>
          <SettingsEditor />
        </section>
        <section>
          <h2 className="mb-3 text-sm font-semibold">Staff</h2>
          <StaffManager />
        </section>
      </div>
    </div>
  );
}
