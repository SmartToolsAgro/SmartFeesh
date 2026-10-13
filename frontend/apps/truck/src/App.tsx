import { createQueryClient, LanguageSwitch, LoginPage, RequireRole, type Session, useLogout } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { Sprite, Toaster, TruckShell, type TruckTab, useFavicon } from "@frutti/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router";

import { ClosingPage } from "./ClosingPage";
import { DayPage } from "./DayPage";
import { ExpensePage } from "./ExpensePage";
import { LossPage } from "./LossPage";
import { forgetSavedData } from "./offline";
import { OfflineBanner } from "./OfflineBanner";
import { PaymentPage } from "./PaymentPage";
import { PickupPage } from "./PickupPage";
import { SalePage } from "./SalePage";
import { ScreenError } from "./ScreenError";
import { StockPage } from "./StockPage";
import { SyncStatus } from "./SyncStatus";

const queryClient = createQueryClient();
// Without signal, ask anyway: the phone answers from what it saved (public/sw.js) instead of waiting forever.
queryClient.setDefaultOptions({ queries: { networkMode: "offlineFirst" } });

// Same four tabs as the approved prototype.
function useTabs(): TruckTab[] {
  const { t } = useTranslation();
  return [
    { to: "/", label: t("truck.tabs.day"), icon: "home" },
    { to: "/stock", label: t("truck.tabs.stock"), icon: "box" },
    { to: "/vente", label: t("truck.tabs.sale"), icon: "receipt" },
    { to: "/cloture", label: t("truck.tabs.closing"), icon: "lock" },
  ];
}

function Shell({ session }: { session: Session }) {
  const { t } = useTranslation();
  const tabs = useTabs();
  const logout = useLogout();
  const location = useLocation();
  useFavicon(session.organization.logo_url);
  return (
    <TruckShell
      tabs={tabs}
      logoUrl={session.organization.logo_url}
      eyebrow={session.truck?.name ?? session.organization.name}
      title={t("truck.hello", { name: session.user.first_name || session.user.username })}
      onLogout={() => {
        void forgetSavedData();
        logout.mutate();
      }}
    >
      <LanguageSwitch className="mb-3 self-end" />
      <OfflineBanner />
      <SyncStatus />
      <ScreenError resetKey={location.pathname}>
        <Outlet />
      </ScreenError>
    </TruckShell>
  );
}

function AppRoutes() {
  const { t } = useTranslation();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage title={t("truck.appName")} withLanguage />} />
      <Route
        element={
          <RequireRole allow={["driver"]} wrongAppMessage={t("truck.wrongApp")}>
            {(session) => <Shell session={session} />}
          </RequireRole>
        }
      >
        <Route path="/" element={<DayPage />} />
        <Route path="/stock" element={<StockPage />} />
        <Route path="/vente" element={<SalePage />} />
        <Route path="/cloture" element={<ClosingPage />} />
        <Route path="/depense" element={<ExpensePage />} />
        <Route path="/encaissement" element={<PaymentPage />} />
        <Route path="/perte" element={<LossPage />} />
        <Route path="/reprise" element={<PickupPage />} />
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
