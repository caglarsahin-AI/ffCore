"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { z } from "zod";

import { useReportError } from "@/components/use-report-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type LoginRequest = components["schemas"]["LoginRequest"];

// POST /auth/login (03a): the backend sets the HttpOnly session cookie; a wrong email or password
// is one 401 invalid_credentials, shown on the form without saying which field was wrong.
// `next` is already checked by safeNext (same-origin path) on the server.
export function LoginForm({ next }: { next: string }) {
  const t = useTranslations("Login");
  const tErrors = useTranslations("Errors");
  const router = useRouter();
  const report = useReportError();
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [pending, setPending] = useState(false);

  const schema = z.object({
    email: z.email(t("emailInvalid")),
    password: z.string().min(1, t("passwordRequired")),
  });

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = schema.safeParse({ email: form.get("email"), password: form.get("password") });
    if (!parsed.success) {
      const fields = z.flattenError(parsed.error).fieldErrors;
      setErrors({ email: fields.email?.[0], password: fields.password?.[0] });
      return;
    }
    setErrors({});
    setPending(true);
    try {
      await api("POST", "/api/v1/auth/login", parsed.data satisfies LoginRequest);
      router.replace(next);
      router.refresh();
    } catch (error) {
      setPending(false);
      if (error instanceof ApiError && error.code === "invalid_credentials") {
        setErrors({ form: tErrors("invalidCredentials") });
      } else {
        report(error);
      }
    }
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
      {errors.form && (
        <p role="alert" className="text-sm text-destructive" data-testid="login-error">
          {errors.form}
        </p>
      )}
      <Button type="submit" disabled={pending}>
        {t("submit")}
      </Button>
    </form>
  );
}
