"use client";

import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Clock } from "lucide-react";

import { Popover } from "@/components/popover";
import { useLang, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/* Date and time pickers drawn by the app, so the open picker uses the app's font
   and colours (the browser's own pickers can't be themed). */

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

const fieldClass =
  "inline-flex h-9 items-center justify-between gap-2 rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none focus-visible:border-primary focus-visible:shadow-[0_0_0_1px_var(--ring)] disabled:cursor-not-allowed disabled:opacity-60";

export function DateField({
  value,
  onChange,
  disabled,
  className,
  placeholder,
  ...rest
}: {
  value: string; // YYYY-MM-DD or ""
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
  "aria-label"?: string;
}) {
  const t = useT();
  const lang = useLang();
  const locale = lang === "id" ? "id-ID" : "en-GB";
  const [open, setOpen] = useState(false);
  const selected = value ? new Date(value + "T00:00:00") : null;
  const [month, setMonth] = useState(() => {
    const d = selected ?? new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });

  const today = iso(new Date());
  const first = (month.getDay() + 6) % 7; // Monday first
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells: (Date | null)[] = [
    ...Array.from({ length: first }, () => null),
    ...Array.from({ length: days }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1)),
  ];
  const weekdays = Array.from({ length: 7 }, (_, i) => t(`day.${i + 1}`)); // Sen … Min
  const shift = (n: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1));

  return (
    <div className="relative inline-block">
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (selected) setMonth(new Date(selected.getFullYear(), selected.getMonth(), 1));
          setOpen(!open);
        }}
        className={cn(fieldClass, className)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={rest["aria-label"]}
      >
        <span className={cn("truncate", !selected && "text-subtle-foreground")}>
          {selected ? selected.toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" }) : placeholder ?? "—"}
        </span>
        <CalendarDays className="size-4 shrink-0 text-muted-foreground" />
      </button>
      <Popover open={open} onClose={() => setOpen(false)} className="right-0 mt-1 w-64 p-3">
        <div className="mb-2 flex items-center justify-between">
          <button type="button" onClick={() => shift(-1)} className="rounded p-1 text-muted-foreground hover:bg-muted" aria-label="‹">
            <ChevronLeft className="size-4" />
          </button>
          <span className="text-sm font-semibold">{month.toLocaleDateString(locale, { month: "long", year: "numeric" })}</span>
          <button type="button" onClick={() => shift(1)} className="rounded p-1 text-muted-foreground hover:bg-muted" aria-label="›">
            <ChevronRight className="size-4" />
          </button>
        </div>
        <div className="grid grid-cols-7 gap-0.5 text-center">
          {weekdays.map((w) => (
            <span key={w} className="pb-1 text-[11px] font-medium text-subtle-foreground">
              {w}
            </span>
          ))}
          {cells.map((d, i) => {
            if (!d) return <span key={`e${i}`} />;
            const key = iso(d);
            return (
              <button
                key={key}
                type="button"
                onClick={() => {
                  onChange(key);
                  setOpen(false);
                }}
                className={cn(
                  "h-8 rounded-md text-sm tabular-nums hover:bg-muted",
                  key === today && "font-semibold text-primary",
                  key === value && "bg-primary font-semibold text-primary-foreground hover:bg-primary",
                )}
              >
                {d.getDate()}
              </button>
            );
          })}
        </div>
        <div className="mt-2 flex justify-between border-t border-divider pt-2 text-xs">
          <button
            type="button"
            className="font-medium text-primary hover:underline"
            onClick={() => {
              onChange(today);
              setOpen(false);
            }}
          >
            {t("common.today")}
          </button>
          {placeholder !== undefined && value && (
            <button
              type="button"
              className="text-muted-foreground hover:underline"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              {t("common.clear")}
            </button>
          )}
        </div>
      </Popover>
    </div>
  );
}

function Column({ count, step = 1, current, onPick }: { count: number; step?: number; current: number; onPick: (n: number) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector("[data-current]")?.scrollIntoView({ block: "center" });
  }, []);
  return (
    <div ref={ref} className="h-52 flex-1 overflow-y-auto pr-0.5">
      {Array.from({ length: Math.ceil(count / step) }, (_, i) => i * step).map((n) => (
        <button
          key={n}
          type="button"
          data-current={n === current ? "" : undefined}
          onClick={() => onPick(n)}
          className={cn(
            "block w-full rounded-md py-1.5 text-center text-sm tabular-nums hover:bg-muted",
            n === current && "bg-primary font-semibold text-primary-foreground hover:bg-primary",
          )}
        >
          {pad(n)}
        </button>
      ))}
    </div>
  );
}

export function TimeField({
  value,
  onChange,
  disabled,
  className,
  ...rest
}: {
  value: string; // HH:MM
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
}) {
  const [open, setOpen] = useState(false);
  const [h, m] = (value || "00:00").split(":").map(Number);
  return (
    <div className="relative inline-block">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={cn(fieldClass, "tabular-nums", className)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={rest["aria-label"]}
      >
        {value || "--:--"}
        <Clock className="size-4 shrink-0 text-muted-foreground" />
      </button>
      <Popover open={open} onClose={() => setOpen(false)} className="right-0 mt-1 flex w-36 min-w-0 gap-1 p-1.5">
        {open && (
          <>
            <Column count={24} current={h} onPick={(n) => onChange(`${pad(n)}:${pad(m)}`)} />
            <Column count={60} current={m} onPick={(n) => { onChange(`${pad(h)}:${pad(n)}`); setOpen(false); }} />
          </>
        )}
      </Popover>
    </div>
  );
}
