"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useStaff, useStaffMutate } from "@/lib/session";

type Setup = { secret: string; uri: string; qr: string };

function TwoFactor() {
  const t = useT();
  const me = useStaff();
  const refreshMe = useStaffMutate();
  const [setup, setSetup] = useState<Setup | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [disabling, setDisabling] = useState(false);

  async function run(fn: () => Promise<unknown>) {
    try {
      await fn();
    } catch (e) {
      toast.error(errorMessage(e, t));
    }
  }

  return (
    <section className="rounded-lg bg-card p-6">
      <div className="flex items-start gap-4">
        <ShieldCheck className={me.totp_enabled ? "mt-0.5 size-5 text-success-foreground" : "mt-0.5 size-5 text-muted-foreground"} />
        <div className="flex-1">
          <h2 className="text-[15px] font-semibold">{t("account.twofa")}</h2>
          <p className="mt-0.5 text-sm text-muted-foreground" data-testid="twofa-state">
            {me.totp_enabled ? t("account.twofaOn") : t("account.twofaOff")}
          </p>
        </div>
        {!me.totp_enabled && !setup && (
          <Button size="sm" onClick={() => run(async () => setSetup(await api<Setup>("/auth/2fa/setup", { method: "POST" })))} data-testid="twofa-setup">
            {t("account.setup")}
          </Button>
        )}
        {me.totp_enabled && !disabling && (
          <Button size="sm" variant="ghost" onClick={() => setDisabling(true)}>
            {t("account.disable")}
          </Button>
        )}
      </div>

      {setup && !me.totp_enabled && (
        <div className="mt-5 grid gap-6 border-t border-divider pt-5 sm:grid-cols-[auto_1fr]">
          {/* eslint-disable-next-line @next/next/no-img-element -- inline SVG data URI */}
          <img src={setup.qr} alt="QR" className="size-44 rounded-md bg-white p-1" data-testid="twofa-qr" />
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await api("/auth/2fa/enable", { json: { code } });
                setSetup(null);
                setCode("");
                await refreshMe();
              });
            }}
          >
            <p className="text-sm">{t("account.scan")}</p>
            <p className="text-xs text-muted-foreground">
              {t("account.manual")} <code className="font-mono text-foreground" data-testid="twofa-secret">{setup.secret}</code>
            </p>
            <div className="flex max-w-xs gap-2">
              <Input
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                maxLength={7}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/[^\d ]/g, ""))}
                className="font-mono tracking-widest"
                data-testid="twofa-code"
              />
              <Button type="submit" disabled={code.replace(/\s/g, "").length !== 6}>
                {t("account.confirm")}
              </Button>
            </div>
          </form>
        </div>
      )}

      {me.totp_enabled && disabling && (
        <form
          className="mt-5 flex max-w-md flex-col gap-2 border-t border-divider pt-5"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await api("/auth/2fa/disable", { json: { password } });
              setPassword("");
              setDisabling(false);
              await refreshMe();
            });
          }}
        >
          <p className="text-sm text-muted-foreground">{t("account.disableHint")}</p>
          <div className="flex gap-2">
            <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <Button type="submit" variant="outline" disabled={!password}>
              {t("account.disable")}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

function Password() {
  const t = useT();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  return (
    <section className="rounded-lg bg-card p-6">
      <h2 className="text-[15px] font-semibold">{t("account.password")}</h2>
      <form
        className="mt-4 grid max-w-xl gap-2 sm:grid-cols-[1fr_1fr_auto]"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api("/auth/password", { json: { current, new: next } });
            setCurrent("");
            setNext("");
            toast.success(t("account.changed"));
          } catch (err) {
            toast.error(errorMessage(err, t));
          }
        }}
      >
        <Input type="password" autoComplete="current-password" placeholder={t("account.current")} value={current} onChange={(e) => setCurrent(e.target.value)} />
        <Input type="password" autoComplete="new-password" placeholder={t("account.new")} value={next} onChange={(e) => setNext(e.target.value)} />
        <Button type="submit" variant="outline" disabled={!current || next.length < 10}>
          {t("account.change")}
        </Button>
      </form>
    </section>
  );
}

export default function AccountPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-4 p-6">
        <TwoFactor />
        <Password />
      </div>
    </div>
  );
}
