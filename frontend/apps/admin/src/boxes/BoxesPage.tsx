import { type BoxMovement, type BoxTypeEnum, useListBoxBalances, useListBoxMovements } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, useTranslation } from "@frutti/i18n";
import { Button, Card, CardTitle, EmptyState, Icon, Pill, PageHeader, Table, Td, Th } from "@frutti/ui";
import { keepPreviousData } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useOutletContext } from "react-router";

import { StockTabs } from "../lib/StockTabs";
import { canRecordReceipts } from "../receipts/shared";
import { canRecordTransfers } from "../transfers/shared";
import {
  BOX_TYPES,
  type HolderCounts,
  type HolderKind,
  HOLDER_KINDS,
  formatBoxCount,
  holdersFromBalances,
  holdersOfKind,
} from "./shared";

const PAGE_SIZE = 50;
const SELECT_CLASSES = "rounded-control border border-line bg-surface px-3 py-2 text-ink";
const LABEL_CLASSES = "flex flex-col gap-1 text-[0.78rem] font-semibold text-ink-2";
const KIND_TONES = {
  opening: "good",
  receive: "good",
  load: "sea",
  leave: "coral",
  collect: "neutral",
  return: "neutral",
  truck_return: "sea",
  write_off: "bad",
} as const;

/** The returnable boxes (caisses): what each holder has now, and the history of moves (P1-T14). Read only. */
export function BoxesPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const balances = useListBoxBalances();
  const holders = useMemo(() => holdersFromBalances(balances.data ?? []), [balances.data]);
  // Boxes come in with a receipt or a load: the places to record them, for whoever may record them.
  const canRecord = canRecordReceipts(session) || canRecordTransfers(session);

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.goods")} title={t("admin.boxes.title")} />
      <StockTabs />
      <p className="text-ink-2">{t("admin.boxes.intro")}</p>

      {balances.data?.length === 0 && (
        <Card className="mt-4 flex flex-col items-start gap-3" data-testid="boxes-empty">
          <p className="text-ink-2">{t("admin.boxes.empty.text")}</p>
          {canRecord && (
            <div className="flex flex-wrap gap-2">
              {canRecordReceipts(session) && (
                <Button variant="primary" onClick={() => void navigate("/achats/nouvelle")}>
                  <Icon name="plus" />
                  {t("admin.boxes.empty.receipt")}
                </Button>
              )}
              {canRecordTransfers(session) && (
                <Button onClick={() => void navigate("/stock/transferts/nouveau")}>
                  <Icon name="truck" />
                  {t("admin.boxes.empty.load")}
                </Button>
              )}
            </div>
          )}
        </Card>
      )}

      {balances.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : balances.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : (
        <div className="grid items-start gap-4 min-[960px]:grid-cols-3">
          {HOLDER_KINDS.map((kind) => (
            <BalanceTable key={kind} kind={kind} holders={holdersOfKind(holders, kind)} />
          ))}
        </div>
      )}

      <BoxHistory holders={holders} />
    </>
  );
}

function BalanceTable({ kind, holders }: { kind: HolderKind; holders: HolderCounts[] }) {
  const { t } = useTranslation();
  return (
    <Card className="min-w-0">
      <CardTitle>{t(`admin.boxes.kinds.${kind}`)}</CardTitle>
      {kind === "supplier" && <p className="mb-3 text-[0.85rem] text-ink-2">{t("admin.boxes.supplierNote")}</p>}
      {holders.length === 0 ? (
        <p className="text-ink-2">{t("admin.boxes.noHolders")}</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>{t("admin.boxes.columns.holder")}</Th>
              <Th numeric>{t("admin.boxes.types.small")}</Th>
              <Th numeric>{t("admin.boxes.types.big")}</Th>
            </tr>
          </thead>
          <tbody>
            {holders.map((holder) => (
              <tr key={holder.id}>
                <Td className="font-semibold">{holder.name || t("admin.boxes.unnamed")}</Td>
                <Td numeric className="num">
                  {formatBoxCount(holder.small)}
                </Td>
                <Td numeric className="num">
                  {formatBoxCount(holder.big)}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </Card>
  );
}

function BoxHistory({ holders }: { holders: HolderCounts[] }) {
  const { t } = useTranslation();
  const [holder, setHolder] = useState("");
  const [boxType, setBoxType] = useState<BoxTypeEnum | "">("");
  const [offset, setOffset] = useState(0);

  const movements = useListBoxMovements(
    {
      limit: PAGE_SIZE,
      offset,
      ...(holder ? { holder: Number(holder) } : {}),
      ...(boxType ? { box_type: boxType } : {}),
    },
    { query: { placeholderData: keepPreviousData } },
  );
  const page = movements.data;
  const list = page?.results ?? [];
  const filtering = holder !== "" || boxType !== "";

  const reset = () => {
    setHolder("");
    setBoxType("");
    setOffset(0);
  };

  return (
    <section className="mt-6 flex flex-col gap-4">
      <CardTitle className="mb-0">{t("admin.boxes.history.title")}</CardTitle>

      <Card className="filter-bar flex flex-wrap items-end gap-3 p-3">
        <label className={LABEL_CLASSES}>
          {t("admin.boxes.history.holder")}
          <select
            className={SELECT_CLASSES}
            value={holder}
            onChange={(event) => {
              setHolder(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t("admin.boxes.history.allHolders")}</option>
            {holders.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name || t("admin.boxes.unnamed")}
              </option>
            ))}
          </select>
        </label>
        <label className={LABEL_CLASSES}>
          {t("admin.boxes.history.boxType")}
          <select
            className={SELECT_CLASSES}
            value={boxType}
            onChange={(event) => {
              setBoxType(event.target.value as BoxTypeEnum | "");
              setOffset(0);
            }}
          >
            <option value="">{t("admin.boxes.history.allBoxTypes")}</option>
            {BOX_TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`admin.boxes.types.${value}`)}
              </option>
            ))}
          </select>
        </label>
        {filtering && <Button onClick={reset}>{t("admin.boxes.history.reset")}</Button>}
        <span className="ms-auto text-[0.85rem] text-ink-2" aria-live="polite">
          {page && t("admin.boxes.history.count", { count: page.count })}
        </span>
      </Card>

      {movements.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : movements.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : list.length === 0 ? (
        filtering ? (
          <p className="text-ink-2">{t("admin.boxes.history.noMatch")}</p>
        ) : (
          <EmptyState illustration="fridge" title={t("admin.boxes.history.empty")} />
        )
      ) : (
        <Card className="p-2">
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.boxes.history.columns.date")}</Th>
                <Th>{t("admin.boxes.history.columns.kind")}</Th>
                <Th>{t("admin.boxes.history.columns.boxType")}</Th>
                <Th numeric>{t("admin.boxes.history.columns.count")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.boxes.history.columns.from")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.boxes.history.columns.to")}</Th>
              </tr>
            </thead>
            <tbody>
              {list.map((movement) => (
                <HistoryRow key={movement.id} movement={movement} />
              ))}
            </tbody>
          </Table>
          {page && page.count > PAGE_SIZE && (
            <div className="flex items-center justify-end gap-2 p-2">
              <span className="me-auto text-[0.85rem] text-ink-2">
                {t("admin.boxes.history.page", {
                  from: offset + 1,
                  to: Math.min(offset + PAGE_SIZE, page.count),
                  count: page.count,
                })}
              </span>
              <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                {t("admin.boxes.history.previous")}
              </Button>
              <Button disabled={!page.next} onClick={() => setOffset(offset + PAGE_SIZE)}>
                {t("admin.boxes.history.next")}
              </Button>
            </div>
          )}
        </Card>
      )}
    </section>
  );
}

function HistoryRow({ movement }: { movement: BoxMovement }) {
  const { t } = useTranslation();
  return (
    <tr>
      <Td className="num whitespace-nowrap">{formatDate(movement.created_at)}</Td>
      <Td>
        <Pill tone={KIND_TONES[movement.kind]}>{t(`admin.boxes.kindLabels.${movement.kind}`)}</Pill>
        {movement.kind === "write_off" && movement.reason && (
          <span className="block text-[0.8rem] text-ink-2">
            {t("admin.boxes.history.reason")}: {movement.reason}
          </span>
        )}
      </Td>
      <Td>{t(`admin.boxes.types.${movement.box_type}`)}</Td>
      <Td numeric className="num">
        {formatBoxCount(movement.count)}
      </Td>
      <Td className="max-[720px]:hidden">{movement.from_holder_name ?? t("admin.boxes.outside")}</Td>
      <Td className="max-[720px]:hidden">{movement.to_holder_name ?? t("admin.boxes.outside")}</Td>
    </tr>
  );
}
