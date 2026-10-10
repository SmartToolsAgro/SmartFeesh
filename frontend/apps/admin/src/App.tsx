import { LoginPage, RequireRole, type Session, useLogout } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
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
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useOutletContext } from "react-router";

import { LocationsPage } from "./locations/LocationsPage";
import { ProductsPage } from "./products/ProductsPage";
import { SupplierDetailPage } from "./suppliers/SupplierDetailPage";
import { SuppliersPage } from "./suppliers/SuppliersPage";

const queryClient = new QueryClient();

// Same modules and order as the approved prototype, plus the catalogue. Each one becomes a real screen in its phase.
function useNav(): AdminNavGroup[] {
  const { t } = useTranslation();
  return [
    { label: t("admin.groups.steering"), items: [{ to: "/", label: t("admin.nav.dashboard"), icon: "grid" }] },
    {
      label: t("admin.groups.sales"),
      items: [
        { to: "/devis", label: t("admin.nav.quotes"), icon: "quote" },
        { to: "/ventes", label: t("admin.nav.sales"), icon: "receipt" },
        { to: "/clients", label: t("admin.nav.customers"), icon: "users" },
      ],
    },
    {
      label: t("admin.groups.goods"),
      items: [
        { to: "/stock", label: t("admin.nav.stock"), icon: "box" },
        { to: "/produits", label: t("admin.nav.products"), icon: "snow" },
        { to: "/achats", label: t("admin.nav.purchases"), icon: "cart" },
        { to: "/fournisseurs", label: t("admin.nav.suppliers"), icon: "anchor" },
      ],
    },
    {
      label: t("admin.groups.finance"),
      items: [
        { to: "/charges", label: t("admin.nav.expenses"), icon: "wallet" },
        { to: "/salaires", label: t("admin.nav.payroll"), icon: "badge" },
        { to: "/partenariats", label: t("admin.nav.profitSharing"), icon: "percent" },
        { to: "/cloture", label: t("admin.nav.closing"), icon: "calcheck" },
      ],
    },
  ];
}

// Screens that exist; every other entry of the menu shows "coming soon".
const SCREENS: Record<string, ReactNode> = {
  "/stock": <LocationsPage />,
  "/produits": <ProductsPage />,
  "/fournisseurs": <SuppliersPage />,
};

const ILLUSTRATIONS: Record<string, IllustrationName> = {
  "/achats": "fish",
  "/ventes": "truck",
};

function displayName(session: Session): string {
  return `${session.user.first_name} ${session.user.last_name}`.trim() || session.user.username;
}

function Shell({ session }: { session: Session }) {
  const { t } = useTranslation();
  const nav = useNav();
  const logout = useLogout();
  return (
    <AdminShell
      nav={nav}
      user={{ name: displayName(session), role: t(`roles.${session.role}`) }}
      onLogout={() => logout.mutate()}
    >
      <Outlet context={session} />
    </AdminShell>
  );
}

function Dashboard() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  return (
    <>
      <PageHeader eyebrow={session.organization.name} title={t("admin.nav.dashboard")} />
      <EmptyState
        illustration="fridge"
        title={t("admin.dashboard.hello", { name: session.user.first_name || session.user.username })}
      >
        {t("admin.dashboard.body")}
      </EmptyState>
    </>
  );
}

function ComingSoon({ path, title, group }: { path: string; title: string; group: string }) {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader eyebrow={group} title={title} />
      <EmptyState illustration={ILLUSTRATIONS[path] ?? "mix"} title={t("common.comingSoon")}>
        {t("common.comingSoonBody")}
      </EmptyState>
    </>
  );
}

function AppRoutes() {
  const { t } = useTranslation();
  const nav = useNav();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage title={t("admin.appName")} />} />
      <Route
        element={
          <RequireRole allow={["owner", "manager", "accountant"]} wrongAppMessage={t("admin.wrongApp")}>
            {(session) => <Shell session={session} />}
          </RequireRole>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/fournisseurs/:supplierId" element={<SupplierDetailPage />} />
        {nav.flatMap((group) =>
          group.items
            .filter((item) => item.to !== "/")
            .map((item) => (
              <Route
                key={item.to}
                path={item.to}
                element={SCREENS[item.to] ?? <ComingSoon path={item.to} title={item.label} group={group.label} />}
              />
            )),
        )}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Sprite />
      <Toaster position="bottom-right" />
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
