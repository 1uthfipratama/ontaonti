"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ContactPanel } from "@/components/inbox/contact-panel";
import { ConversationList, type Filters } from "@/components/inbox/conversation-list";
import { Thread } from "@/components/inbox/thread";

function Inbox() {
  const params = useSearchParams();
  const router = useRouter();
  const selected = params.get("c") ? Number(params.get("c")) : null;
  const [filters, setFilters] = useState<Filters>({
    channel: "",
    status: "OPEN",
    flag: params.get("flag") ?? "",
    mode: "",
    q: "",
  });

  return (
    <div className="grid h-full grid-cols-[20rem_1fr_17rem]">
      <ConversationList
        filters={filters}
        setFilters={setFilters}
        selected={selected}
        onSelect={(id) => router.push(`/inbox?c=${id}`)}
      />
      {selected ? (
        <Thread key={selected} id={selected} />
      ) : (
        <div className="flex items-center justify-center text-sm text-muted-foreground">
          Select a conversation
        </div>
      )}
      {selected ? <ContactPanel id={selected} /> : <div className="border-l" />}
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
