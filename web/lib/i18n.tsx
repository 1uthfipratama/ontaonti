"use client";

import { useCallback, useSyncExternalStore } from "react";

import { dict, type Lang } from "@/lib/dict";

/* Staff UI language: Indonesian by default, English on request. Stored per
   browser. useSyncExternalStore renders the server default ("id") during
   hydration and then the stored choice, so there is no hydration mismatch. */

const KEY = "lang";
const listeners = new Set<() => void>();

function read(): Lang {
  try {
    return localStorage.getItem(KEY) === "en" ? "en" : "id";
  } catch {
    return "id";
  }
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function setLang(lang: Lang) {
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* private mode: keep the in-memory default */
  }
  document.documentElement.lang = lang;
  listeners.forEach((l) => l());
}

export function useLang(): Lang {
  return useSyncExternalStore(subscribe, read, () => "id");
}

export type T = (key: string, vars?: Record<string, string | number>) => string;

/** t("inbox.reply") or t("time.minutes", { n: 5 }). Falls back to English, then the key. */
export function useT(): T {
  const lang = useLang();
  return useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let s = dict[lang][key] ?? dict.en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [lang],
  );
}
