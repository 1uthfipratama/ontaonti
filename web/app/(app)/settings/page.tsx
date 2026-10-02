"use client";

import { ChannelStatus } from "@/components/settings/channels";

export default function SettingsPage() {
  return (
    <div className="h-full space-y-6 overflow-y-auto p-6">
      <section>
        <h1 className="mb-3 text-lg font-semibold">Channels</h1>
        <ChannelStatus />
      </section>
    </div>
  );
}
