"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { z } from "zod";

import { notConnected } from "@/components/not-connected";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// Form fields from PLAN 5 (email, password). The request body follows the 03a contract and is
// wired in 10a-binding; until then submitting reports "not connected" instead of faking a login.
export function LoginForm() {
  const t = useTranslations("Login");
  const tState = useTranslations("State");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});

  const schema = z.object({
    email: z.email(t("emailInvalid")),
    password: z.string().min(1, t("passwordRequired")),
  });

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = schema.safeParse({ email: form.get("email"), password: form.get("password") });
    if (!parsed.success) {
      const fields = z.flattenError(parsed.error).fieldErrors;
      setErrors({ email: fields.email?.[0], password: fields.password?.[0] });
      return;
    }
    setErrors({});
    notConnected(tState("notConnected"));
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate data-testid="login-form">
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">{t("email")}</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? "email-error" : undefined}
        />
        {errors.email && (
          <p id="email-error" className="text-sm text-destructive">
            {errors.email}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="password">{t("password")}</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? "password-error" : undefined}
        />
        {errors.password && (
          <p id="password-error" className="text-sm text-destructive">
            {errors.password}
          </p>
        )}
      </div>
      <Button type="submit">{t("submit")}</Button>
    </form>
  );
}
