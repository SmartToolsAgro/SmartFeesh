import { type FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router";

import { ApiError } from "./api";
import { useLogin, useSession } from "./session";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "Trop de tentatives. Réessayez dans une minute.";
    if (error.status === 401 || error.status === 403) return error.message;
  }
  return "Connexion impossible. Vérifiez le réseau puis réessayez.";
}

/** Login screen shared by both apps. Plain markup for now: the design system arrives in P0-T07. */
export function LoginPage({ title }: { title: string }) {
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

  return (
    <main>
      <h1>{title}</h1>
      <form onSubmit={submit} aria-label="Connexion">
        <p>
          <label htmlFor="login-username">Identifiant</label>
          <input
            id="login-username"
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </p>
        <p>
          <label htmlFor="login-password">Mot de passe</label>
          <input
            id="login-password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </p>
        {login.isError && <p role="alert">{messageFor(login.error)}</p>}
        <button type="submit" disabled={login.isPending}>
          {login.isPending ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </main>
  );
}
