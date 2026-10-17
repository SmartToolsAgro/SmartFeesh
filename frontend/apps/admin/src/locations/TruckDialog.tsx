import {
  archiveTruck,
  type ConditionEnum,
  createTruck,
  restoreTruck,
  type Truck,
  updateTruck,
  useListMembers,
} from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import {
  Button,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  Field,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";

import { fieldErrors } from "../lib/errors";
import { refreshLocations } from "./shared";

type Errors = Partial<Record<"name" | "plate" | "driver" | "detail", string>>;

// Radix Select cannot hold an empty value: this one stands for "no driver".
const NO_DRIVER = "none";

/** Create a truck (`truck` absent) or change one. Owners and managers only; the server checks it too. */
export function TruckDialog({ truck, onDone }: { truck?: Truck; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const formId = useId();
  const members = useListMembers();
  const [name, setName] = useState(truck?.name ?? "");
  const [plate, setPlate] = useState(truck?.plate ?? "");
  const [driver, setDriver] = useState(truck?.driver ? String(truck.driver.id) : NO_DRIVER);
  const [condition, setCondition] = useState<ConditionEnum>(truck?.condition ?? "ok");
  const [errors, setErrors] = useState<Errors>({});

  const drivers = (members.data ?? []).filter((member) => member.role === "driver" && member.is_active);

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        name: name.trim(),
        plate: plate.trim(),
        driver: driver === NO_DRIVER ? null : Number(driver),
        condition,
      };
      return truck ? updateTruck(truck.id, payload) : createTruck(payload);
    },
    onSuccess: async () => {
      toast.success(t(truck ? "admin.locations.form.saved" : "admin.locations.form.truckCreated"));
      await refreshLocations(queryClient);
      onDone();
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.locations.form.error") });
    },
  });

  const toggleActive = useMutation({
    mutationFn: (target: Truck) => (target.is_active ? archiveTruck(target.id) : restoreTruck(target.id)),
    onSuccess: async (saved) => {
      toast.success(t(saved.is_active ? "admin.locations.form.restoredDone" : "admin.locations.form.archivedDone"));
      await refreshLocations(queryClient);
      onDone();
    },
    // A location still holding stock cannot be archived: the server says why.
    onError: (failure) => {
      setErrors({ detail: fieldErrors(failure).detail ?? t("admin.locations.form.error") });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!name.trim()) found.name = t("admin.locations.form.required");
    if (!plate.trim()) found.plate = t("admin.locations.form.required");
    setErrors(found);
    if (Object.keys(found).length === 0) save.mutate();
  }

  return (
    <DialogContent>
      <DialogTitle>
        {t(truck ? "admin.locations.form.editTruckTitle" : "admin.locations.form.createTruckTitle")}
      </DialogTitle>
      <DialogDescription className="sr-only">
        {truck?.name ?? t("admin.locations.form.createTruckTitle")}
      </DialogDescription>

      <form id={formId} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label={t("admin.locations.form.name")} htmlFor={`${formId}-name`} error={errors.name}>
          <Input
            id={`${formId}-name`}
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-invalid={errors.name ? true : undefined}
            autoComplete="off"
          />
        </Field>
        <Field label={t("admin.locations.form.plate")} htmlFor={`${formId}-plate`} error={errors.plate}>
          <Input
            id={`${formId}-plate`}
            value={plate}
            onChange={(event) => setPlate(event.target.value)}
            aria-invalid={errors.plate ? true : undefined}
            aria-describedby={`${formId}-plate-hint`}
            autoComplete="off"
            className="num"
          />
          <p id={`${formId}-plate-hint`} className="text-[0.8rem] text-ink-2">
            {t("admin.locations.form.plateHint")}
          </p>
        </Field>
        <Field label={t("admin.locations.form.driver")} htmlFor={`${formId}-driver`} error={errors.driver}>
          <Select value={driver} onValueChange={setDriver}>
            <SelectTrigger id={`${formId}-driver`} aria-invalid={errors.driver ? true : undefined}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_DRIVER}>{t("admin.locations.noDriver")}</SelectItem>
              {/* Until the member list arrives, the current driver still shows by name. */}
              {truck?.driver && !drivers.some(({ user }) => user.id === truck.driver?.id) && (
                <SelectItem value={String(truck.driver.id)}>{truck.driver.name}</SelectItem>
              )}
              {drivers.map(({ user }) => {
                const fullName = `${user.first_name} ${user.last_name}`.trim() || user.username;
                return (
                  <SelectItem key={user.id} value={String(user.id)}>
                    {fullName}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
          <p className="text-[0.8rem] text-ink-2">{t("admin.locations.form.driverHint")}</p>
        </Field>
        <Field label={t("admin.locations.form.condition")} htmlFor={`${formId}-condition`}>
          <Select value={condition} onValueChange={(value) => setCondition(value as ConditionEnum)}>
            <SelectTrigger id={`${formId}-condition`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(["ok", "maintenance", "breakdown"] as const).map((value) => (
                <SelectItem key={value} value={value}>
                  {t(`admin.locations.conditions.${value}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[0.8rem] text-ink-2">{t("admin.locations.form.conditionHint")}</p>
        </Field>
      </form>

      {errors.detail && (
        <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
          {errors.detail}
        </p>
      )}

      <DialogFooter className="items-center">
        {truck && (
          <Button
            variant="ghost"
            className="me-auto"
            disabled={toggleActive.isPending}
            onClick={() => toggleActive.mutate(truck)}
          >
            {t(truck.is_active ? "admin.locations.form.archive" : "admin.locations.form.restore")}
          </Button>
        )}
        <Button onClick={onDone}>{t("admin.locations.form.cancel")}</Button>
        <Button type="submit" form={formId} variant="primary" disabled={save.isPending}>
          {save.isPending ? t("admin.locations.form.saving") : t("admin.locations.form.save")}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
