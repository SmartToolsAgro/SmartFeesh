import { createQueryClient, LoginPage, RequireRole, type Session, useLogout } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { EmptyState, type IllustrationName, Sprite, Toaster, TruckShell, type TruckTab } from "@frutti/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router";

import { DayPage } from "./DayPage";
import { ExpensePage } from "./ExpensePage";
import { SalePage } from "./SalePage";

const queryClient = createQueryClient();

// Same four tabs as the approved prototype. Each one becomes a real screen in Phase 3.
function useTabs(): (TruckTab & { illustration: IllustrationName })[] {
  const { t } = useTranslation();
  return [
    { to: "/", label: t("truck.tabs.day"), icon: "home", illustration: "truck" },
    { to: "/stock", label: t("truck.tabs.stock"), icon: "box", illustration: "shrimp" },
    { to: "/vente", label: t("truck.tabs.sale"), icon: "receipt", illustration: "fish" },
    { to: "/cloture", label: t("truck.tabs.closing"), icon: "lock", illustration: "fridge" },
  ];
}

function Shell({ session }: { session: Session }) {
  const { t } = useTranslation();
  const tabs = useTabs();
  const logout = useLogout();
  return (
    <TruckShell
      tabs={tabs}
      eyebrow={session.truck?.name ?? session.organization.name}
      title={t("truck.hello", { name: session.user.first_name || session.user.username })}
      onLogout={() => logout.mutate()}
    >
      <Outlet />
    </TruckShell>
  );
}

function ComingSoon({ title, illustration }: { title: string; illustration: IllustrationName }) {
  const { t } = useTranslation();
  return (
    <EmptyState illustration={illustration} title={title}>
      {t("common.comingSoonBody")}
    </EmptyState>
  );
}

function AppRoutes() {
  const { t } = useTranslation();
  const tabs = useTabs();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage title={t("truck.appName")} />} />
      <Route
        element={
          <RequireRole allow={["driver"]} wrongAppMessage={t("truck.wrongApp")}>
            {(session) => <Shell session={session} />}
          </RequireRole>
        }
      >
        <Route path="/" element={<DayPage />} />
        <Route path="/vente" element={<SalePage />} />
        <Route path="/depense" element={<ExpensePage />} />
        {tabs
          .filter((tab) => tab.to !== "/" && tab.to !== "/vente")
          .map((tab) => (
            <Route
              key={tab.to}
              path={tab.to}
              element={<ComingSoon title={tab.label} illustration={tab.illustration} />}
            />
          ))}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Sprite />
      <Toaster />
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
