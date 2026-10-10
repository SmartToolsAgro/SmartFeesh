import {
  archiveLocation,
  createLocation,
  restoreLocation,
  type StockLocation,
  StockLocationCreateKindEnum,
  updateLocation,
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

type Kind = (typeof StockLocationCreateKindEnum)[keyof typeof StockLocationCreateKindEnum];
type Errors = Partial<Record<"kind" | "name" | "detail", string>>;

/** Create a cold room or other location (`location` absent) or change one. Trucks have their own dialog. */
export function LocationDialog({ location, onDone }: { location?: StockLocation; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const formId = useId();
  const [kind, setKind] = useState<Kind>(StockLocationCreateKindEnum.cold_room);
  const [name, setName] = useState(location?.name ?? "");
  const [counterSales, setCounterSales] = useState(location?.counter_sales ?? true);
  const [errors, setErrors] = useState<Errors>({});

  const save = useMutation({
    mutationFn: () =>
      location
        ? updateLocation(location.id, { name: name.trim(), counter_sales: counterSales })
        : createLocation({ kind, name: name.trim(), counter_sales: counterSales }),
    onSuccess: async () => {
      toast.success(t(location ? "admin.locations.form.saved" : "admin.locations.form.created"));
      await refreshLocations(queryClient);
      onDone();
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.locations.form.error") });
    },
  });

  const toggleActive = useMutation({
    mutationFn: (target: StockLocation) => (target.is_active ? archiveLocation(target.id) : restoreLocation(target.id)),
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
    if (!name.trim()) {
      setErrors({ name: t("admin.locations.form.required") });
      return;
    }
    setErrors({});
    save.mutate();
  }

  return (
    <DialogContent>
      <DialogTitle>
        {t(location ? "admin.locations.form.editRoomTitle" : "admin.locations.form.createRoomTitle")}
      </DialogTitle>
      <DialogDescription className="sr-only">
        {location?.name ?? t("admin.locations.form.createRoomTitle")}
      </DialogDescription>

      <form id={formId} onSubmit={submit} noValidate className="flex flex-col gap-4">
        {!location && (
          <Field label={t("admin.locations.form.kind")} htmlFor={`${formId}-kind`} error={errors.kind}>
            <Select value={kind} onValueChange={(value) => setKind(value as Kind)}>
              <SelectTrigger id={`${formId}-kind`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.values(StockLocationCreateKindEnum).map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(`admin.locations.kinds.${value}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        )}
        <Field label={t("admin.locations.form.name")} htmlFor={`${formId}-name`} error={errors.name}>
          <Input
            id={`${formId}-name`}
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-invalid={errors.name ? true : undefined}
            autoComplete="off"
          />
        </Field>
        <label className="flex items-center gap-2.5 text-[0.9rem]">
          <input
            type="checkbox"
            checked={counterSales}
            onChange={(event) => setCounterSales(event.target.checked)}
            className="size-4 accent-sea"
          />
          {t("admin.locations.form.counterSales")}
        </label>
      </form>

      {errors.detail && (
        <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
          {errors.detail}
        </p>
      )}

      <DialogFooter className="items-center">
        {location && (
          <Button
            variant="ghost"
            className="me-auto"
            disabled={toggleActive.isPending}
            onClick={() => toggleActive.mutate(location)}
          >
            {t(location.is_active ? "admin.locations.form.archive" : "admin.locations.form.restore")}
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
