import { LoginPage, RequireRole, type Session, useLogout } from "@frutti/auth";
import { BRAND } from "@frutti/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

const queryClient = new QueryClient();

// Scaffold screen. The real shell (phone layout, bottom navigation) comes in P0-T07.
function Home({ session }: { session: Session }) {
  const logout = useLogout();
  const name = `${session.user.first_name} ${session.user.last_name}`.trim() || session.user.username;
  return (
    <main>
      <h1>{BRAND.name}</h1>
      <p>Espace chauffeur · {session.organization.name}</p>
      <p>
        Connecté : <strong>{name}</strong>
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
          <Route path="/login" element={<LoginPage title={`${BRAND.name} · Chauffeur`} />} />
          <Route
            path="/"
            element={
              <RequireRole
                allow={["driver"]}
                wrongAppMessage="Ce compte n'est pas un compte chauffeur. Utilisez l'application d'administration."
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
