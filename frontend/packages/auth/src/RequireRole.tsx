import { Button, Card } from "@frutti/ui";
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

function Notice({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-dvh place-items-center p-4">
      <Card className="flex w-full max-w-[420px] flex-col items-start gap-4">{children}</Card>
    </main>
  );
}

/** Route guard: sends logged-out visitors to /login and turns away roles that belong to the other app. */
export function RequireRole({ allow, wrongAppMessage, children }: Props) {
  const session = useSession();
  const logout = useLogout();
  const location = useLocation();

  if (session.isPending) {
    return (
      <p role="status" className="p-6 text-ink-2">
        Chargement…
      </p>
    );
  }
  if (session.isError) {
    return (
      <Notice>
        <p role="alert">Serveur injoignable. Vérifiez le réseau puis rechargez la page.</p>
      </Notice>
    );
  }
  if (session.data === null) return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  if (!allow.includes(session.data.role)) {
    return (
      <Notice>
        <p role="alert">{wrongAppMessage}</p>
        <Button onClick={() => logout.mutate()} disabled={logout.isPending}>
          Se déconnecter
        </Button>
      </Notice>
    );
  }

  return <>{children(session.data)}</>;
}
