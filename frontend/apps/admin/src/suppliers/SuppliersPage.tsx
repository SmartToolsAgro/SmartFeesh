import { useListSuppliers } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { Button, Card, Dialog, EmptyState, Icon, Input, PageHeader, Pill, Table, Td, Th } from "@frutti/ui";
import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router";

import { type Status, StatusFilter } from "../lib/StatusFilter";
import { useDebounced } from "../lib/useDebounced";
import { canEditSuppliers } from "./shared";
import { SupplierDialog } from "./SupplierDialog";

export function SuppliersPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const canEdit = canEditSuppliers(session);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<Status>("active");
  const [creating, setCreating] = useState(false);
  const query = useDebounced(search.trim());

  const suppliers = useListSuppliers(
    { status, ...(query ? { search: query } : {}) },
    { query: { placeholderData: keepPreviousData } },
  );
  const list = suppliers.data ?? [];
  const filtering = query !== "" || status !== "active";

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.goods")} title={t("admin.suppliers.title")}>
        {canEdit && (
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Icon name="plus" />
            {t("admin.suppliers.add")}
          </Button>
        )}
      </PageHeader>

      {!canEdit && <p className="text-ink-2">{t("admin.suppliers.readOnly")}</p>}

      <Card className="filter-bar flex flex-wrap items-center gap-3 p-3">
        <Input
          type="search"
          aria-label={t("admin.suppliers.search")}
          placeholder={t("admin.suppliers.search")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="min-w-52 flex-[2_1_14rem]"
        />
        <StatusFilter
          value={status}
          onChange={setStatus}
          label={t("admin.suppliers.show")}
          labels={{
            active: t("admin.suppliers.status.active"),
            archived: t("admin.suppliers.status.archived"),
            all: t("admin.suppliers.status.all"),
          }}
        />
        <span className="ms-auto text-[0.85rem] text-ink-2" aria-live="polite">
          {suppliers.data && t("admin.suppliers.count", { count: list.length })}
        </span>
      </Card>

      {suppliers.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : suppliers.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : list.length === 0 ? (
        filtering ? (
          <p className="text-ink-2">{t("admin.suppliers.noMatch")}</p>
        ) : (
          <EmptyState illustration="shrimp" title={t("admin.suppliers.empty")}>
            {t("admin.suppliers.emptyBody")}
          </EmptyState>
        )
      ) : (
        <Card className="p-2">
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.suppliers.columns.reference")}</Th>
                <Th>{t("admin.suppliers.columns.name")}</Th>
                <Th>{t("admin.suppliers.columns.phone")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.suppliers.columns.taxId")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.suppliers.columns.contacts")}</Th>
              </tr>
            </thead>
            <tbody>
              {list.map((supplier) => (
                // The name is the link; a click anywhere on the row opens the same page.
                <tr
                  key={supplier.id}
                  onClick={() => void navigate(`/fournisseurs/${supplier.id}`)}
                  className="cursor-pointer hover:bg-surface-2"
                >
                  <Td className="num whitespace-nowrap text-ink-2">{supplier.reference}</Td>
                  <Td>
                    <Link
                      to={`/fournisseurs/${supplier.id}`}
                      className="font-semibold text-ink hover:underline"
                      onClick={(event) => event.stopPropagation()}
                    >
                      {supplier.name}
                    </Link>
                    {!supplier.is_active && (
                      <Pill className="ms-2" tone="neutral">
                        {t("admin.suppliers.archived")}
                      </Pill>
                    )}
                    {supplier.city && <div className="text-[0.8rem] text-ink-2">{supplier.city}</div>}
                  </Td>
                  <Td className="num whitespace-nowrap">{supplier.phone}</Td>
                  <Td className="num whitespace-nowrap max-[720px]:hidden">{supplier.tax_id}</Td>
                  <Td className="text-ink-2 max-[720px]:hidden">
                    {supplier.contacts.length > 0 &&
                      t("admin.suppliers.contactsCount", { count: supplier.contacts.length })}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        {creating && (
          <SupplierDialog
            onDone={(created) => {
              setCreating(false);
              if (created) void navigate(`/fournisseurs/${created.id}`);
            }}
          />
        )}
      </Dialog>
    </>
  );
}
