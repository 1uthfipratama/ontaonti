"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

/** Minimal anchored panel: place inside a `relative` wrapper. Closes on outside
 *  click and Escape. */
export function Popover({
  open,
  onClose,
  className,
  children,
}: {
  open: boolean;
  onClose: () => void;
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const down = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", down);
      document.removeEventListener("keydown", key);
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      ref={ref}
      className={cn(
        "absolute z-30 min-w-56 rounded-lg bg-popover p-1.5 text-popover-foreground shadow-[0_10px_15px_-3px_rgba(0,0,0,0.12),0_4px_6px_-2px_rgba(0,0,0,0.06)] ring-1 ring-border",
        className,
      )}
    >
      {children}
    </div>
  );
}
