import { LoginPage, RequireRole, type Role, type Session, useLogout } from "@frutti/auth";
import {
  type AdminNavGroup,
  AdminShell,
  EmptyState,
  type IllustrationName,
  PageHeader,
  Sprite,
  Toaster,
} from "@frutti/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useOutletContext } from "react-router";

const queryClient = new QueryClient();

const ROLE_LABELS: Record<Role, string> = {
  owner: "Propriétaire",
  manager: "Gestionnaire",
  accountant: "Comptable",
  driver: "Chauffeur",
};

// Same modules and order as the approved prototype. Each one becomes a real screen in its phase.
const NAV: AdminNavGroup[] = [
  { label: "Pilotage", items: [{ to: "/", label: "Tableau de bord", icon: "grid" }] },
  {
    label: "Commercial",
    items: [
      { to: "/devis", label: "Devis", icon: "quote" },
      { to: "/ventes", label: "Ventes & factures", icon: "receipt" },
      { to: "/clients", label: "Clients", icon: "users" },
    ],
  },
  {
    label: "Marchandise",
    items: [
      { to: "/stock", label: "Stock frigo & camions", icon: "box" },
      { to: "/achats", label: "Achats", icon: "cart" },
      { to: "/fournisseurs", label: "Fournisseurs", icon: "anchor" },
    ],
  },
  {
    label: "Finances",
    items: [
      { to: "/charges", label: "Charges", icon: "wallet" },
      { to: "/salaires", label: "Personnel & salaires", icon: "badge" },
      { to: "/partenariats", label: "Partage des bénéfices", icon: "percent" },
      { to: "/cloture", label: "Clôture mensuelle", icon: "calcheck" },
    ],
  },
];

const ILLUSTRATIONS: Record<string, IllustrationName> = {
  "/stock": "fridge",
  "/achats": "fish",
  "/fournisseurs": "shrimp",
  "/ventes": "truck",
};

function displayName(session: Session): string {
  return `${session.user.first_name} ${session.user.last_name}`.trim() || session.user.username;
}

function Shell({ session }: { session: Session }) {
  const logout = useLogout();
  return (
    <AdminShell
      nav={NAV}
      user={{ name: displayName(session), role: ROLE_LABELS[session.role] }}
      onLogout={() => logout.mutate()}
    >
      <Outlet context={session} />
    </AdminShell>
  );
}

function Dashboard() {
  const session = useOutletContext<Session>();
  return (
    <>
      <PageHeader eyebrow={session.organization.name} title="Tableau de bord" />
      <EmptyState illustration="fridge" title={`Bonjour ${session.user.first_name || session.user.username}`}>
        Le socle est en place. Les indicateurs du jour apparaîtront ici dès que le stock et les ventes seront
        enregistrés dans l'application.
      </EmptyState>
    </>
  );
}

function ComingSoon({ path, title, group }: { path: string; title: string; group: string }) {
  return (
    <>
      <PageHeader eyebrow={group} title={title} />
      <EmptyState illustration={ILLUSTRATIONS[path] ?? "mix"} title="Bientôt disponible">
        Cet écran sera construit dans une prochaine étape du projet.
      </EmptyState>
    </>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Sprite />
      <Toaster position="bottom-right" />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage title="Administration" />} />
          <Route
            element={
              <RequireRole
                allow={["owner", "manager", "accountant"]}
                wrongAppMessage="Ce compte est un compte chauffeur. Utilisez l'application chauffeur."
              >
                {(session) => <Shell session={session} />}
              </RequireRole>
            }
          >
            <Route path="/" element={<Dashboard />} />
            {NAV.flatMap((group) =>
              group.items
                .filter((item) => item.to !== "/")
                .map((item) => (
                  <Route
                    key={item.to}
                    path={item.to}
                    element={<ComingSoon path={item.to} title={item.label} group={group.label} />}
                  />
                )),
            )}
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
