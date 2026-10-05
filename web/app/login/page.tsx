"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { LangToggle } from "@/components/lang-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function LoginPage() {
  const t = useT();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [needCode, setNeedCode] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", { json: { email, password, code: needCode ? code : undefined } });
      router.replace("/inbox");
    } catch (err) {
      // Accounts with two-factor login: the password was right, now ask for the code.
      if (err instanceof ApiError && err.message === "Two-factor code required") {
        setNeedCode(true);
        return;
      }
      setError(errorMessage(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center p-4">
      <div className="absolute top-4 right-4 flex items-center gap-1">
        <LangToggle className="mr-1" />
        <ThemeToggle />
      </div>
      <div className="w-full max-w-sm rounded-lg bg-card p-8 shadow-[0_2px_4px_rgba(39,43,50,0.06)]">
        <div className="mb-6 flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
            OE
          </div>
          <div className="leading-tight">
            <div className="font-semibold">Onti Erlina</div>
            <div className="text-xs text-muted-foreground">{t("login.subtitle")}</div>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-xs text-muted-foreground">{t("login.email")}</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password" className="text-xs text-muted-foreground">{t("login.password")}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {needCode && (
            <div className="space-y-1.5">
              <Label htmlFor="code" className="text-xs text-muted-foreground">{t("login.code")}</Label>
              <Input
                id="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                maxLength={7}
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, ""))}
                required
                className="font-mono tracking-widest"
              />
              <p className="text-xs text-muted-foreground">{t("login.codeHint")}</p>
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? t("login.submitting") : t("login.submit")}
          </Button>
        </form>
      </div>
      <p className="mt-4 text-xs text-subtle-foreground">{t("login.prototype")}</p>
    </div>
  );
}
