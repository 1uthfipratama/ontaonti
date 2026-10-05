"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Field = {
  key: string;
  label: string;
  type: "text" | "textarea" | "number" | "bool" | "select" | "time" | "days";
  value: string | number | boolean | number[];
  default: string | number | boolean | number[];
  choices: string[];
  overridden: boolean;
};
type Rules = { categories: Record<string, { severity: string; keywords: string[] }> };
type SettingsData = { groups: { name: string; fields: Field[] }[]; flag_rules: Rules; flag_rules_overridden: boolean };

/** A field, or an Indonesian/English pair of the same text shown as one field. */
type Item = { base: string; id: Field; en?: Field };

function pair(fields: Field[]): Item[] {
  const out: Item[] = [];
  for (const f of fields) {
    if (f.key.endsWith("_en")) continue;
    const base = f.key.endsWith("_id") ? f.key.slice(0, -3) : f.key;
    const en = f.key.endsWith("_id") ? fields.find((x) => x.key === `${base}_en`) : undefined;
    out.push({ base, id: f, en });
  }
  return out;
}

const RULES = "__rules";

export function SettingsEditor({ only }: { only?: string[] }) {
  const t = useT();
  const { mutate } = useSWRConfig();
  const { data } = useSWR<SettingsData>("/settings");
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [rulesDraft, setRulesDraft] = useState<Rules | null>(null);
  const [busy, setBusy] = useState(false);
  const [group, setGroup] = useState<string | null>(null);
  const [en, setEn] = useState<Record<string, boolean>>({});
  if (!data) return null;

  const groups = data.groups.filter((g) => (only ? only.includes(g.name) : true));
  const showRules = !only;
  const active = group ?? groups[0]?.name;
  const dirty = Object.keys(draft).length > 0 || rulesDraft !== null;
  const val = (f: Field) => (f.key in draft ? draft[f.key] : f.value);
  const set = (key: string, v: unknown) => setDraft({ ...draft, [key]: v });
  const rules = rulesDraft ?? data.flag_rules;
  const label = (base: string, f: Field) => {
    const k = `set.${base}`;
    const s = t(k);
    return s === k ? f.label : s;
  };

  async function save() {
    setBusy(true);
    try {
      const values: Record<string, unknown> = { ...draft };
      if (rulesDraft) values.flag_rules = rulesDraft;
      const next = await api<SettingsData>("/settings", { method: "PUT", json: { values } });
      mutate("/settings", next, { revalidate: false });
      setDraft({});
      setRulesDraft(null);
      toast.success(t("common.saved"));
    } catch (e) {
      toast.error(errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  }

  async function reset(keys: string[]) {
    try {
      const next = await api<SettingsData>("/settings/reset", { json: { keys } });
      mutate("/settings", next, { revalidate: false });
      const d = { ...draft };
      keys.forEach((k) => delete d[k]);
      setDraft(d);
      if (keys.includes("flag_rules")) setRulesDraft(null);
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  function editRules(cat: string, patch: Partial<{ severity: string; keywords: string[] }>) {
    const next: Rules = JSON.parse(JSON.stringify(rules));
    Object.assign(next.categories[cat], patch);
    setRulesDraft(next);
  }

  function input(f: Field, big: boolean) {
    const v = val(f);
    switch (f.type) {
      case "textarea":
        return (
          <Textarea
            id={f.key}
            value={String(v)}
            onChange={(e) => set(f.key, e.target.value)}
            className={big ? "min-h-72 font-mono text-xs" : "min-h-24"}
          />
        );
      case "number":
        return (
          <Input
            id={f.key}
            type="number"
            step="any"
            className="max-w-48"
            value={String(v)}
            onChange={(e) => set(f.key, e.target.value === "" ? "" : Number(e.target.value))}
          />
        );
      case "bool":
        return <Switch id={f.key} checked={Boolean(v)} onCheckedChange={(x) => set(f.key, x)} />;
      case "time":
        return (
          <Input id={f.key} type="time" className="max-w-36" value={String(v)} onChange={(e) => set(f.key, e.target.value)} />
        );
      case "days": {
        const on = new Set((v as number[]) ?? []);
        return (
          <div className="flex flex-wrap gap-1.5" id={f.key}>
            {[1, 2, 3, 4, 5, 6, 7].map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={on.has(d)}
                onClick={() => set(f.key, on.has(d) ? [...on].filter((x) => x !== d) : [...on, d].sort())}
                className={cn(
                  "h-8 w-12 rounded-md text-sm font-medium",
                  on.has(d) ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground",
                )}
              >
                {t(`day.${d}`)}
              </button>
            ))}
          </div>
        );
      }
      case "select":
        return (
          <NativeSelect
            id={f.key}
            value={String(v)}
            onChange={(e) => set(f.key, e.target.value)}
            options={f.choices.map((c) => ({ value: c, label: t(`choice.${c}`) === `choice.${c}` ? c : t(`choice.${c}`) }))}
          />
        );
      default:
        return <Input id={f.key} className="max-w-md" value={String(v)} onChange={(e) => set(f.key, e.target.value)} />;
    }
  }

  const current = groups.find((g) => g.name === active);
  return (
    <div className="grid gap-4 md:grid-cols-[13rem_1fr]">
      <nav className="space-y-0.5">
        {[...groups.map((g) => g.name), ...(showRules ? [RULES] : [])].map((name) => (
          <button
            key={name}
            onClick={() => setGroup(name)}
            className={cn(
              "block w-full rounded-md px-3 py-2 text-left text-sm",
              active === name ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {name === RULES ? t("ed.rules") : t(`ed.group.${name}`)}
          </button>
        ))}
      </nav>

      <div className="min-w-0 space-y-4">
        <div className="space-y-6 rounded-lg bg-card p-5">
          {active !== RULES &&
            current &&
            pair(current.fields).map((it) => {
              const showEn = it.en && en[it.base];
              const f = showEn ? it.en! : it.id;
              const overridden = it.id.overridden || it.en?.overridden;
              return (
                <div key={it.base} className="space-y-1.5">
                  <div className="flex items-center gap-3">
                    <label htmlFor={f.key} className="text-sm font-medium">
                      {label(it.base, f)}
                    </label>
                    {it.en && (
                      <span className="flex text-[11px] font-semibold" aria-label={t("ed.language")}>
                        {(["id", "en"] as const).map((l) => (
                          <button
                            key={l}
                            onClick={() => setEn({ ...en, [it.base]: l === "en" })}
                            className={cn(
                              "px-1.5 uppercase",
                              (l === "en") === Boolean(showEn) ? "text-foreground" : "text-subtle-foreground hover:text-foreground",
                            )}
                          >
                            {l}
                          </button>
                        ))}
                      </span>
                    )}
                    <span className="flex-1" />
                    {overridden && (
                      <button
                        className="text-[11px] font-medium text-primary hover:underline"
                        onClick={() => reset([it.id.key, ...(it.en ? [it.en.key] : [])])}
                      >
                        {t("ed.reset")}
                      </button>
                    )}
                  </div>
                  {input(f, it.base === "persona_prompt")}
                  {t(`set.${it.base}.hint`) !== `set.${it.base}.hint` && (
                    <p className="text-xs text-muted-foreground">{t(`set.${it.base}.hint`)}</p>
                  )}
                </div>
              );
            })}

          {active === RULES && (
            <>
              <div className="flex items-center gap-3">
                <p className="flex-1 text-xs text-muted-foreground">{t("ed.rulesHint")}</p>
                {data.flag_rules_overridden && (
                  <button className="text-[11px] font-medium text-primary hover:underline" onClick={() => reset(["flag_rules"])}>
                    {t("ed.reset")}
                  </button>
                )}
              </div>
              <div className="grid gap-5 lg:grid-cols-2">
                {Object.entries(rules.categories).map(([cat, spec]) => (
                  <div key={cat} className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="flex-1 text-sm font-medium first-letter:uppercase">
                        {t(`cat.${cat.toLowerCase()}`) === `cat.${cat.toLowerCase()}` ? cat.toLowerCase() : t(`cat.${cat.toLowerCase()}`)}
                      </span>
                      <NativeSelect
                        value={spec.severity}
                        onChange={(e) => editRules(cat, { severity: e.target.value })}
                        options={["low", "high", "emergency"].map((s) => ({ value: s, label: t(`sev.${s}`) }))}
                      />
                    </div>
                    <Textarea
                      data-testid={`rules-${cat}`}
                      className="min-h-40 font-mono text-xs"
                      value={spec.keywords.join("\n")}
                      onChange={(e) =>
                        editRules(cat, { keywords: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })
                      }
                    />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {dirty && (
          <div className="sticky bottom-4 flex items-center gap-3 rounded-lg bg-card px-5 py-3 shadow-[0_10px_15px_-3px_rgba(0,0,0,0.12)] ring-1 ring-border">
            <span className="flex-1 text-sm text-muted-foreground">{t("ed.unsaved")}</span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setDraft({});
                setRulesDraft(null);
              }}
            >
              {t("ed.discard")}
            </Button>
            <Button size="sm" onClick={save} disabled={busy} data-testid="settings-save">
              {t("common.save")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
