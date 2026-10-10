import { ApiError } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Brand, Button, Card, Field, Input, ThemeToggle } from "@frutti/ui";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router";

import { useLogin, useSession } from "./session";

/** Login screen shared by both apps. `title` names the app ("Administration", "Chauffeur"). */
export function LoginPage({ title }: { title: string }) {
  const { t } = useTranslation();
  const session = useSession();
  const login = useLogin();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  if (session.data) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from ?? "/"} replace />;
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate({ username: username.trim(), password });
  }

  function errorMessage(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 429) return t("auth.tooManyAttempts");
      // The server explains a refused login in the user's language.
      if (error.status === 401 || error.status === 403) return error.message;
    }
    return t("auth.networkError");
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-radial-[60%_70%_at_70%_40%] from-sea-soft to-transparent p-4">
      <Card className="flex w-full max-w-[380px] flex-col gap-5 p-6">
        <div className="flex items-center justify-between gap-3">
          <Brand />
          <ThemeToggle />
        </div>
        <div>
          <span className="eyebrow">{title}</span>
          <h1 className="text-[1.4rem]">{t("auth.title")}</h1>
        </div>
        <form onSubmit={submit} aria-label={t("auth.title")} className="flex flex-col gap-4">
          <Field label={t("auth.username")} htmlFor="login-username">
            <Input
              id="login-username"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </Field>
          <Field label={t("auth.password")} htmlFor="login-password">
            <Input
              id="login-password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          {login.isError && (
            <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
              {errorMessage(login.error)}
            </p>
          )}
          <Button type="submit" variant="primary" size="lg" disabled={login.isPending}>
            {login.isPending ? t("auth.submitting") : t("auth.submit")}
          </Button>
        </form>
      </Card>
    </main>
  );
}
