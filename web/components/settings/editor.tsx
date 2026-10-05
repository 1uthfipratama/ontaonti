"use client";

import { useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import { toast } from "sonner";

import { NativeSelect } from "@/components/native-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";

type Field = {
  key: string;
  label: string;
  type: "text" | "textarea" | "number" | "bool" | "select";
  value: string | number | boolean;
  default: string | number | boolean;
  choices: string[];
  overridden: boolean;
};
type Rules = { categories: Record<string, { severity: string; keywords: string[] }> };
type SettingsData = { groups: { name: string; fields: Field[] }[]; flag_rules: Rules; flag_rules_overridden: boolean };

export function SettingsEditor() {
  const { mutate } = useSWRConfig();
  const { data } = useSWR<SettingsData>("/settings");
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [rulesDraft, setRulesDraft] = useState<Rules | null>(null);
  const [busy, setBusy] = useState(false);
  if (!data) return null;

  const dirty = Object.keys(draft).length > 0 || rulesDraft !== null;
  const val = (f: Field) => (f.key in draft ? draft[f.key] : f.value);
  const set = (key: string, v: unknown) => setDraft({ ...draft, [key]: v });
  const rules = rulesDraft ?? data.flag_rules;

  async function save() {
    setBusy(true);
    try {
      const values: Record<string, unknown> = { ...draft };
      if (rulesDraft) values.flag_rules = rulesDraft;
      const next = await api<SettingsData>("/settings", { method: "PUT", json: { values } });
      mutate("/settings", next, { revalidate: false });
      setDraft({});
      setRulesDraft(null);
      toast.success("Settings saved");
    } catch (e) {
      toast.error(errorMessage(e));
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
      toast.success("Reset to default");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }

  function editKeywords(cat: string, text: string) {
    const next: Rules = JSON.parse(JSON.stringify(rules));
    next.categories[cat].keywords = text.split("\n").map((s) => s.trim()).filter(Boolean);
    setRulesDraft(next);
  }
  function editSeverity(cat: string, sev: string) {
    const next: Rules = JSON.parse(JSON.stringify(rules));
    next.categories[cat].severity = sev;
    setRulesDraft(next);
  }

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 flex items-center gap-3 rounded-lg bg-card px-5 py-3 shadow-[0_2px_4px_rgba(39,43,50,0.06)]">
        <span className="flex-1 text-sm text-muted-foreground">{dirty ? "You have unsaved changes" : "All changes saved"}</span>
        <Button size="sm" onClick={save} disabled={!dirty || busy} data-testid="settings-save">
          Save
        </Button>
        {dirty && (
          <Button size="sm" variant="ghost" onClick={() => { setDraft({}); setRulesDraft(null); }}>
            Discard
          </Button>
        )}
      </div>

      {data.groups.map((g) => (
        <Card key={g.name}>
          <CardHeader>
            <CardTitle className="text-sm">{g.name}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            {g.fields.map((f) => (
              <div key={f.key} className={f.type === "textarea" ? "space-y-1 md:col-span-2" : "space-y-1"}>
                <div className="flex items-center gap-2">
                  <label htmlFor={f.key} className="text-xs font-medium text-muted-foreground">
                    {f.label}
                  </label>
                  {f.overridden && (
                    <button className="text-[11px] font-medium text-primary hover:underline" onClick={() => reset([f.key])}>
                      Reset to default
                    </button>
                  )}
                </div>
                {f.type === "textarea" && (
                  <Textarea
                    id={f.key}
                    value={String(val(f))}
                    onChange={(e) => set(f.key, e.target.value)}
                    className={f.key === "persona_prompt" ? "min-h-64 font-mono text-xs" : "min-h-20 text-xs"}
                  />
                )}
                {f.type === "text" && <Input id={f.key} value={String(val(f))} onChange={(e) => set(f.key, e.target.value)} />}
                {f.type === "number" && (
                  <Input
                    id={f.key}
                    type="number"
                    step="any"
                    value={String(val(f))}
                    onChange={(e) => set(f.key, e.target.value === "" ? "" : Number(e.target.value))}
                  />
                )}
                {f.type === "bool" && (
                  <input id={f.key} type="checkbox" checked={Boolean(val(f))} onChange={(e) => set(f.key, e.target.checked)} />
                )}
                {f.type === "select" && (
                  <NativeSelect
                    id={f.key}
                    value={String(val(f))}
                    onChange={(e) => set(f.key, e.target.value)}
                    options={f.choices.map((c) => ({ value: c, label: c }))}
                  />
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      ))}

      <Card>
        <CardHeader className="flex flex-row items-center">
          <CardTitle className="flex-1 text-sm">Safety keyword rules</CardTitle>
          {data.flag_rules_overridden && (
            <button className="text-xs font-medium text-primary hover:underline" onClick={() => reset(["flag_rules"])}>
              Reset to config/flags.yaml
            </button>
          )}
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            One keyword or phrase per line. Matching ignores case, accents and punctuation, tolerates suffixes
            (-nya, -ku) and up to 2 words in between. These rules always run, even over budget.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            {Object.entries(rules.categories).map(([cat, spec]) => (
              <div key={cat} className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="flex-1 text-xs font-semibold">{cat.charAt(0) + cat.slice(1).toLowerCase().replace("_", " ")}</span>
                  <NativeSelect
                    value={spec.severity}
                    onChange={(e) => editSeverity(cat, e.target.value)}
                    options={["low", "high", "emergency"].map((s) => ({ value: s, label: s }))}
                  />
                </div>
                <Textarea
                  data-testid={`rules-${cat}`}
                  className="min-h-40 font-mono text-xs"
                  value={spec.keywords.join("\n")}
                  onChange={(e) => editKeywords(cat, e.target.value)}
                />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
