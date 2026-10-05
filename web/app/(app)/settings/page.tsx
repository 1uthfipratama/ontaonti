"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ChannelStatus } from "@/components/settings/channels";
import { SettingsEditor } from "@/components/settings/editor";
import { LabelManager } from "@/components/settings/labels";
import { SavedReplies } from "@/components/settings/saved-replies";
import { StaffManager } from "@/components/settings/staff";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "bot", label: "settings.botSafety", el: <SettingsEditor /> },
  { key: "replies", label: "settings.replies", el: <SavedReplies /> },
  { key: "labels", label: "settings.labels", el: <LabelManager /> },
  { key: "channels", label: "settings.channels", el: <ChannelStatus /> },
  { key: "staff", label: "settings.staff", el: <StaffManager /> },
];

function Settings() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const tab = TABS.find((x) => x.key === params.get("tab")) ?? TABS[0];
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl p-6">
        <div className="mb-5 flex gap-1 overflow-x-auto border-b border-border">
          {TABS.map((x) => (
            <button
              key={x.key}
              onClick={() => router.replace(`/settings?tab=${x.key}`)}
              data-testid={`settings-tab-${x.key}`}
              className={cn(
                "-mb-px shrink-0 border-b-2 px-3 py-2 text-sm",
                x.key === tab.key
                  ? "border-primary font-semibold text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t(x.label)}
            </button>
          ))}
        </div>
        {tab.el}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense>
      <Settings />
    </Suspense>
  );
}
