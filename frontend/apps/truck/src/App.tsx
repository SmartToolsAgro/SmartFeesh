import {
  createQueryClient,
  LanguageSwitch,
  LoginPage,
  RequireRole,
  type Session,
  useLogout,
  useSession,
} from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { Sprite, Toaster, TruckShell, type TruckTab, useFavicon } from "@frutti/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router";

import { BackToDay } from "./BackToDay";
import { ClosingPage } from "./ClosingPage";
import { DayPage } from "./DayPage";
import { ExpensePage } from "./ExpensePage";
import { HistoryDayPage, HistoryPage } from "./HistoryPage";
import { LossPage } from "./LossPage";
import { forgetSavedData } from "./offline";
import { useTruckStock } from "./myStock";
import { OfflineBanner } from "./OfflineBanner";
import { PaymentPage } from "./PaymentPage";
import { PickupPage } from "./PickupPage";
import { PriceNotice } from "./PriceNotice";
import { usePriceWatch } from "./priceWatch";
import { SalePage } from "./SalePage";
import { ScreenError } from "./ScreenError";
import { StockPage } from "./StockPage";
import { SyncStatus } from "./SyncStatus";

const queryClient = createQueryClient();
// Without signal, ask anyway: the phone answers from what it saved (public/sw.js) instead of waiting forever.
queryClient.setDefaultOptions({ queries: { networkMode: "offlineFirst" } });

// The phone remembers the company logo it last saw, so the login screen's tab shows it too (D-125). Not a secret:
// it is the logo every document already carries. Storage can be blocked: then the default icon stays.
const LOGO_KEY = "frutti-truck-logo";

function rememberedLogo(): string | null {
  try {
    return localStorage.getItem(LOGO_KEY);
  } catch {
    return null;
  }
}

function remember(logo: string): void {
  try {
    localStorage.setItem(LOGO_KEY, logo);
  } catch {
    // Not saved: the next login screen shows the default icon until a login works again.
  }
}

/** The browser-tab icon: the company logo once known, else the logo remembered on this phone. */
function TabIcon() {
  const session = useSession();
  const logo = session.data?.organization.logo_url ?? null;
  useEffect(() => {
    if (logo) remember(logo);
  }, [logo]);
  useFavicon(logo ?? rememberedLogo());
  return null;
}

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
  // The prices are watched on every screen, so a change is announced wherever the driver is (P3-T02).
  const stock = useTruckStock(session.truck !== null);
  usePriceWatch(stock.data);
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
      <PriceNotice />
      <SyncStatus />
      <ScreenError resetKey={location.pathname}>
        <Outlet />
      </ScreenError>
      <BackToDay pathname={location.pathname} />
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
        <Route path="/historique" element={<HistoryPage />} />
        <Route path="/historique/:dayId" element={<HistoryDayPage />} />
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
        <TabIcon />
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
