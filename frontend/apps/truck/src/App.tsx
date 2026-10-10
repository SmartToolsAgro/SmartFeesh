import { LoginPage, RequireRole, type Session, useLogout } from "@frutti/auth";
import { EmptyState, type IllustrationName, Sprite, Toaster, TruckShell, type TruckTab } from "@frutti/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router";

const queryClient = new QueryClient();

// Same four tabs as the approved prototype. Each one becomes a real screen in Phase 3.
const TABS: (TruckTab & { illustration: IllustrationName })[] = [
  { to: "/", label: "Ma journée", icon: "home", illustration: "truck" },
  { to: "/stock", label: "Mon stock", icon: "box", illustration: "shrimp" },
  { to: "/vente", label: "Vente", icon: "receipt", illustration: "fish" },
  { to: "/cloture", label: "Clôture", icon: "lock", illustration: "fridge" },
];

function Shell({ session }: { session: Session }) {
  const logout = useLogout();
  return (
    <TruckShell
      tabs={TABS}
      eyebrow={session.truck?.name ?? session.organization.name}
      title={`Bonjour ${session.user.first_name || session.user.username}`}
      onLogout={() => logout.mutate()}
    >
      <Outlet />
    </TruckShell>
  );
}

function ComingSoon({ title, illustration }: { title: string; illustration: IllustrationName }) {
  return (
    <EmptyState illustration={illustration} title={title}>
      Cet écran sera construit dans une prochaine étape du projet.
    </EmptyState>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Sprite />
      <Toaster />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage title="Chauffeur" />} />
          <Route
            element={
              <RequireRole
                allow={["driver"]}
                wrongAppMessage="Ce compte n'est pas un compte chauffeur. Utilisez l'application d'administration."
              >
                {(session) => <Shell session={session} />}
              </RequireRole>
            }
          >
            {TABS.map((tab) => (
              <Route
                key={tab.to}
                path={tab.to}
                element={<ComingSoon title={tab.label} illustration={tab.illustration} />}
              />
            ))}
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
