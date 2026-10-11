import { createQueryClient, LoginPage, RequireRole, type Session, useLogout } from "@frutti/auth";
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
import { QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useOutletContext } from "react-router";

import { EmployeeDetailPage } from "./hr/EmployeeDetailPage";
import { EmployeesPage } from "./hr/EmployeesPage";
import { PayrollPage } from "./hr/PayrollPage";
import { LocationsPage } from "./locations/LocationsPage";
import { BatchStockPage } from "./stock/BatchStockPage";
import { MovementsPage } from "./stock/MovementsPage";
import { ProductStockPage } from "./stock/ProductStockPage";
import { PriceBoardPage } from "./prices/PriceBoardPage";
import { ProductsPage } from "./products/ProductsPage";
import { QuoteDetailPage } from "./quotes/QuoteDetailPage";
import { QuoteEditPage, QuoteFormPage } from "./quotes/QuoteFormPage";
import { QuotesPage } from "./quotes/QuotesPage";
import { SupplierInvoiceDetailPage } from "./purchasing/SupplierInvoiceDetailPage";
import { SupplierInvoiceFormPage } from "./purchasing/SupplierInvoiceFormPage";
import { SupplierInvoicesPage } from "./purchasing/SupplierInvoicesPage";
import { SupplierPaymentFormPage } from "./purchasing/SupplierPaymentFormPage";
import { SupplierPaymentsPage } from "./purchasing/SupplierPaymentsPage";
import { ReceiptDetailPage } from "./receipts/ReceiptDetailPage";
import { ReceiptFormPage } from "./receipts/ReceiptFormPage";
import { ReceiptsPage } from "./receipts/ReceiptsPage";
import { CustomerDetailPage } from "./customers/CustomerDetailPage";
import { CustomersPage } from "./customers/CustomersPage";
import { SupplierDetailPage } from "./suppliers/SupplierDetailPage";
import { SuppliersPage } from "./suppliers/SuppliersPage";
import { CountPage } from "./counts/CountPage";
import { CountsPage } from "./counts/CountsPage";
import { LossDetailPage } from "./losses/LossDetailPage";
import { LossesPage } from "./losses/LossesPage";
import { LossFormPage } from "./losses/LossFormPage";
import { TransferDetailPage } from "./transfers/TransferDetailPage";
import { TransferEditPage, TransferFormPage } from "./transfers/TransferFormPage";
import { TransfersPage } from "./transfers/TransfersPage";

const queryClient = createQueryClient();

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
        { to: "/prix", label: t("admin.nav.prices"), icon: "badge" },
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
  "/achats": <ReceiptsPage />,
  "/fournisseurs": <SuppliersPage />,
  "/clients": <CustomersPage />,
  "/prix": <PriceBoardPage />,
  "/devis": <QuotesPage />,
  "/salaires": <PayrollPage />,
};

const ILLUSTRATIONS: Record<string, IllustrationName> = {
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
        <Route path="/clients/:customerId" element={<CustomerDetailPage />} />
        {/* Employees and payroll (P5-T04) */}
        <Route path="/salaires/employes" element={<EmployeesPage />} />
        <Route path="/salaires/employes/:employeeId" element={<EmployeeDetailPage />} />
        {/* Quotes (P2-T03) */}
        <Route path="/devis/nouveau" element={<QuoteFormPage />} />
        <Route path="/devis/:quoteId" element={<QuoteDetailPage />} />
        <Route path="/devis/:quoteId/modifier" element={<QuoteEditPage />} />
        <Route path="/achats/nouvelle" element={<ReceiptFormPage />} />
        <Route path="/achats/:receiptId" element={<ReceiptDetailPage />} />
        <Route path="/achats/factures" element={<SupplierInvoicesPage />} />
        <Route path="/achats/factures/nouvelle" element={<SupplierInvoiceFormPage />} />
        <Route path="/achats/factures/:invoiceId" element={<SupplierInvoiceDetailPage />} />
        <Route path="/achats/factures/:invoiceId/modifier" element={<SupplierInvoiceFormPage />} />
        <Route path="/achats/paiements" element={<SupplierPaymentsPage />} />
        <Route path="/achats/paiements/nouveau" element={<SupplierPaymentFormPage />} />
        {/* Stock screens (P1-T11) */}
        <Route path="/stock/mouvements" element={<MovementsPage />} />
        <Route path="/stock/produits/:productId" element={<ProductStockPage />} />
        <Route path="/stock/lots/:batchId" element={<BatchStockPage />} />
        {/* Stock sections (P1-T09) */}
        <Route path="/stock/transferts" element={<TransfersPage />} />
        <Route path="/stock/transferts/nouveau" element={<TransferFormPage />} />
        <Route path="/stock/transferts/:transferId" element={<TransferDetailPage />} />
        <Route path="/stock/transferts/:transferId/modifier" element={<TransferEditPage />} />
        {/* Stock sections (P1-T10) */}
        <Route path="/stock/pertes" element={<LossesPage />} />
        <Route path="/stock/pertes/nouvelle" element={<LossFormPage />} />
        <Route path="/stock/pertes/:lossId" element={<LossDetailPage />} />
        <Route path="/stock/inventaires" element={<CountsPage />} />
        <Route path="/stock/inventaires/:countId" element={<CountPage />} />
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
