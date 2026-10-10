import { useListLocations, useListTrucks } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { Button, Card, cn, Dialog, Icon, Illustration, type IllustrationName, PageHeader, Pill } from "@frutti/ui";
import { keepPreviousData } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { useOutletContext } from "react-router";

import { type Status, StatusFilter } from "../lib/StatusFilter";
import { LocationDialog } from "./LocationDialog";
import { canEditLocations } from "./shared";
import { TruckDialog } from "./TruckDialog";

type Open = { kind: "room" | "truck"; id: number | "new" } | null;

/** A location card like the prototype's: drawing, name, a line below and status labels. */
function PlaceCard({
  illustration,
  title,
  subtitle,
  pills,
  numeric = false,
  onOpen,
}: {
  illustration: IllustrationName;
  title: string;
  subtitle: ReactNode;
  pills: ReactNode;
  // The subtitle is a plate or another code: fixed-width digits.
  numeric?: boolean;
  onOpen?: () => void;
}) {
  const body = (
    <>
      <div className="grid h-16 w-[86px] flex-none place-items-center rounded-[10px] bg-surface-2">
        <Illustration name={illustration} className="h-[58px] w-20" />
      </div>
      <div className="flex min-w-0 flex-col items-start gap-1 text-start">
        <h3 className="max-w-full truncate" title={title}>
          {title}
        </h3>
        <span className={cn("text-[0.82rem] text-ink-2", numeric && "num")}>{subtitle}</span>
        <span className="flex flex-wrap gap-1.5">{pills}</span>
      </div>
    </>
  );
  return (
    <Card className="p-0" role="article" aria-label={title}>
      {onOpen ? (
        <button
          type="button"
          onClick={onOpen}
          className="flex w-full items-center gap-3.5 rounded-card p-4 hover:bg-surface-2/60"
        >
          {body}
        </button>
      ) : (
        <div className="flex items-center gap-3.5 p-4">{body}</div>
      )}
    </Card>
  );
}

export function LocationsPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const canEdit = canEditLocations(session);
  const [status, setStatus] = useState<Status>("active");
  const [open, setOpen] = useState<Open>(null);

  const locations = useListLocations({ status }, { query: { placeholderData: keepPreviousData } });
  const trucks = useListTrucks({ status }, { query: { placeholderData: keepPreviousData } });
  const rooms = (locations.data ?? []).filter((location) => location.kind !== "truck");
  const truckList = trucks.data ?? [];
  const editingRoom = open?.kind === "room" ? rooms.find((room) => room.id === open.id) : undefined;
  const editingTruck = open?.kind === "truck" ? truckList.find((truck) => truck.id === open.id) : undefined;
  const failed = locations.isError || trucks.isError;
  const loading = locations.isPending || trucks.isPending;

  const archivedPill = (active: boolean) => !active && <Pill tone="neutral">{t("admin.locations.archived")}</Pill>;

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.goods")} title={t("admin.locations.title")}>
        {canEdit && (
          <>
            <Button onClick={() => setOpen({ kind: "room", id: "new" })}>
              <Icon name="snow" />
              {t("admin.locations.addRoom")}
            </Button>
            <Button onClick={() => setOpen({ kind: "truck", id: "new" })}>
              <Icon name="truck" />
              {t("admin.locations.addTruck")}
            </Button>
          </>
        )}
      </PageHeader>

      <p className="text-ink-2">{t(canEdit ? "admin.locations.intro" : "admin.locations.readOnly")}</p>

      <div className="flex">
        <StatusFilter
          value={status}
          onChange={setStatus}
          label={t("admin.locations.show")}
          labels={{
            active: t("admin.locations.status.active"),
            archived: t("admin.locations.status.archived"),
            all: t("admin.locations.status.all"),
          }}
        />
      </div>

      {loading ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : failed ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : (
        <>
          <section aria-labelledby="rooms-title" className="flex flex-col gap-3">
            <h2 id="rooms-title">{t("admin.locations.rooms")}</h2>
            {rooms.length === 0 ? (
              <p className="text-ink-2">{t("admin.locations.noRooms")}</p>
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
                {rooms.map((room) => (
                  <PlaceCard
                    key={room.id}
                    illustration="fridge"
                    title={room.name}
                    subtitle={t(`admin.locations.kinds.${room.kind}`)}
                    pills={
                      <>
                        {room.counter_sales && <Pill tone="sea">{t("admin.locations.counterSales")}</Pill>}
                        {archivedPill(room.is_active)}
                      </>
                    }
                    onOpen={canEdit ? () => setOpen({ kind: "room", id: room.id }) : undefined}
                  />
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="trucks-title" className="flex flex-col gap-3">
            <h2 id="trucks-title">{t("admin.locations.trucks")}</h2>
            {truckList.length === 0 ? (
              <p className="text-ink-2">{t("admin.locations.noTrucks")}</p>
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
                {truckList.map((truck) => (
                  <PlaceCard
                    key={truck.id}
                    illustration="truck"
                    title={truck.driver ? `${truck.name} · ${truck.driver.name}` : truck.name}
                    subtitle={truck.plate}
                    numeric
                    pills={
                      <>
                        {!truck.driver && truck.is_active && <Pill tone="warn">{t("admin.locations.noDriver")}</Pill>}
                        {archivedPill(truck.is_active)}
                      </>
                    }
                    onOpen={canEdit ? () => setOpen({ kind: "truck", id: truck.id }) : undefined}
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}

      <Dialog open={open !== null} onOpenChange={(isOpen) => !isOpen && setOpen(null)}>
        {open?.kind === "room" && open.id === "new" && <LocationDialog onDone={() => setOpen(null)} />}
        {editingRoom && <LocationDialog key={editingRoom.id} location={editingRoom} onDone={() => setOpen(null)} />}
        {open?.kind === "truck" && open.id === "new" && <TruckDialog onDone={() => setOpen(null)} />}
        {editingTruck && <TruckDialog key={editingTruck.id} truck={editingTruck} onDone={() => setOpen(null)} />}
      </Dialog>
    </>
  );
}
