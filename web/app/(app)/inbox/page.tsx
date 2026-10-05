"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ContactPanel } from "@/components/inbox/contact-panel";
import { ConversationList, type Filters } from "@/components/inbox/conversation-list";
import { Thread } from "@/components/inbox/thread";
import { useT } from "@/lib/i18n";

function Inbox() {
  const params = useSearchParams();
  const router = useRouter();
  const t = useT();
  const selected = params.get("c") ? Number(params.get("c")) : null;
  const [filters, setFilters] = useState<Filters>({
    channel: "",
    status: "OPEN",
    flag: params.get("flag") ?? "",
    mode: "",
    label: "",
    q: "",
  });

  return (
    <div className="grid h-full grid-rows-[minmax(0,1fr)] grid-cols-[17rem_minmax(0,1fr)] xl:grid-cols-[20rem_minmax(0,1fr)_18rem]">
      <ConversationList
        filters={filters}
        setFilters={setFilters}
        selected={selected}
        onSelect={(id) => router.push(`/inbox?c=${id}`)}
      />
      {selected ? (
        <Thread key={selected} id={selected} />
      ) : (
        <div className="flex items-center justify-center bg-card text-sm text-muted-foreground">
          {t("inbox.select")}
        </div>
      )}
      <div className="hidden min-h-0 xl:block">
        {selected ? <ContactPanel id={selected} /> : <div className="h-full border-l border-border bg-card" />}
      </div>
    </div>
  );
}

export default function InboxPage() {
  return (
    <Suspense>
      <Inbox />
    </Suspense>
  );
}
