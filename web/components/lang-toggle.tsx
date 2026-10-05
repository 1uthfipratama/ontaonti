"use client";

import { setLang, useLang, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** "ID | EN": quiet text switch for the staff UI language. */
export function LangToggle({ className }: { className?: string }) {
  const lang = useLang();
  const t = useT();
  return (
    <div className={cn("flex items-center text-xs font-semibold", className)} role="group" aria-label={t("common.language")}>
      {(["id", "en"] as const).map((l, i) => (
        <span key={l} className="flex items-center">
          {i > 0 && <span className="px-1 text-border">|</span>}
          <button
            type="button"
            onClick={() => setLang(l)}
            aria-pressed={lang === l}
            data-testid={`lang-${l}`}
            className={cn(
              "rounded px-1 py-0.5 transition-colors",
              lang === l ? "text-foreground" : "text-subtle-foreground hover:text-foreground",
            )}
          >
            {l.toUpperCase()}
          </button>
        </span>
      ))}
    </div>
  );
}
