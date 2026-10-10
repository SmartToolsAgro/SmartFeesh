import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { type Role, type Session, useLogout, useSession } from "./session";

interface Props {
  /** Roles allowed in this app. The server enforces the same rule on every endpoint. */
  allow: readonly Role[];
  /** Shown to a logged-in user whose role belongs to the other app. */
  wrongAppMessage: string;
  children: (session: Session) => ReactNode;
}

/** Route guard: sends logged-out visitors to /login and turns away roles that belong to the other app. */
export function RequireRole({ allow, wrongAppMessage, children }: Props) {
  const session = useSession();
  const logout = useLogout();
  const location = useLocation();

  if (session.isPending) return <p role="status">Chargement…</p>;
  if (session.isError) return <p role="alert">Serveur injoignable. Vérifiez le réseau puis rechargez la page.</p>;
  if (session.data === null) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  if (!allow.includes(session.data.role)) {
    return (
      <main>
        <p role="alert">{wrongAppMessage}</p>
        <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>
          Se déconnecter
        </button>
      </main>
    );
  }

  return <>{children(session.data)}</>;
}
