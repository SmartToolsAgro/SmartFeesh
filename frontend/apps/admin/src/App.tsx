import { LoginPage, RequireRole, type Session, useLogout } from "@frutti/auth";
import { BRAND } from "@frutti/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

const queryClient = new QueryClient();

const ROLE_LABELS = { owner: "Propriétaire", manager: "Gestionnaire", accountant: "Comptable", driver: "Chauffeur" };

// Scaffold screen. The real shell (sidebar, top bar) comes in P0-T07.
function Home({ session }: { session: Session }) {
  const logout = useLogout();
  const name = `${session.user.first_name} ${session.user.last_name}`.trim() || session.user.username;
  return (
    <main>
      <h1>{BRAND.name}</h1>
      <p>Espace administration · {session.organization.name}</p>
      <p>
        Connecté : <strong>{name}</strong> ({ROLE_LABELS[session.role]})
      </p>
      <button type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>
        Se déconnecter
      </button>
    </main>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage title={`${BRAND.name} · Administration`} />} />
          <Route
            path="/"
            element={
              <RequireRole
                allow={["owner", "manager", "accountant"]}
                wrongAppMessage="Ce compte est un compte chauffeur. Utilisez l'application chauffeur."
              >
                {(session) => <Home session={session} />}
              </RequireRole>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
