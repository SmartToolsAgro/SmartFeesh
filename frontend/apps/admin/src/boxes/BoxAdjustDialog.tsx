import { adjustBoxes, type BoxAdjustmentWriteKindEnum, type BoxTypeEnum, useListLocations } from "@frutti/api";
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
import { BOX_TYPES } from "./shared";

type Errors = Partial<Record<"location" | "count" | "reason" | "kind" | "detail", string>>;

/** Boxes bought (they come in) or lost or broken (they go out, with the reason): done from the office. The cost of
 * bought boxes is entered as an expense. */
export function BoxAdjustDialog({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const formId = useId();
  const locations = useListLocations({ status: "active" });
  const places = (locations.data ?? []).filter((place) => place.kind === "cold_room" || place.kind === "truck");
  const [kind, setKind] = useState<BoxAdjustmentWriteKindEnum>("purchase");
  const [location, setLocation] = useState("");
  const [boxType, setBoxType] = useState<BoxTypeEnum>("small");
  const [count, setCount] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});

  const save = useMutation({
    mutationFn: () =>
      adjustBoxes({ kind, location: Number(location), box_type: boxType, count: Number(count), reason: reason.trim() }),
    onSuccess: async () => {
      toast.success(t("admin.boxes.adjust.saved"));
      await queryClient.invalidateQueries({
        predicate: (query) => typeof query.queryKey[0] === "string" && query.queryKey[0].startsWith("/api/v1/boxes"),
      });
      onDone();
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.boxes.adjust.error") });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!location) found.location = t("admin.boxes.adjust.required");
    if (!/^[1-9]\d*$/.test(count.trim())) found.count = t("admin.boxes.adjust.countInvalid");
    if (kind === "write_off" && !reason.trim()) found.reason = t("admin.boxes.adjust.reasonRequired");
    setErrors(found);
    if (Object.keys(found).length === 0) save.mutate();
  }

  return (
    <DialogContent>
      <DialogTitle>{t("admin.boxes.adjust.title")}</DialogTitle>
      <DialogDescription>{t("admin.boxes.adjust.hint")}</DialogDescription>
      <form id={formId} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label={t("admin.boxes.adjust.kind")} htmlFor={`${formId}-kind`} error={errors.kind}>
          <Select value={kind} onValueChange={(value) => setKind(value as BoxAdjustmentWriteKindEnum)}>
            <SelectTrigger id={`${formId}-kind`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="purchase">{t("admin.boxes.kindLabels.purchase")}</SelectItem>
              <SelectItem value="write_off">{t("admin.boxes.kindLabels.write_off")}</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label={t("admin.boxes.adjust.place")} htmlFor={`${formId}-place`} error={errors.location}>
          <Select value={location} onValueChange={setLocation}>
            <SelectTrigger id={`${formId}-place`} aria-invalid={errors.location ? true : undefined}>
              <SelectValue placeholder={t("admin.boxes.adjust.placeHint")} />
            </SelectTrigger>
            <SelectContent>
              {places.map((place) => (
                <SelectItem key={place.id} value={String(place.id)}>
                  {place.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label={t("admin.boxes.adjust.boxType")} htmlFor={`${formId}-type`}>
            <Select value={boxType} onValueChange={(value) => setBoxType(value as BoxTypeEnum)}>
              <SelectTrigger id={`${formId}-type`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {BOX_TYPES.map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(`admin.boxes.types.${value}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={t("admin.boxes.adjust.count")} htmlFor={`${formId}-count`} error={errors.count}>
            <Input
              id={`${formId}-count`}
              inputMode="numeric"
              className="num text-end"
              value={count}
              onChange={(event) => setCount(event.target.value)}
              aria-invalid={errors.count ? true : undefined}
              autoComplete="off"
            />
          </Field>
        </div>
        <Field
          label={t(kind === "write_off" ? "admin.boxes.adjust.reason" : "admin.boxes.adjust.note")}
          htmlFor={`${formId}-reason`}
          error={errors.reason}
        >
          <Input
            id={`${formId}-reason`}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            aria-invalid={errors.reason ? true : undefined}
            autoComplete="off"
          />
        </Field>
      </form>
      {errors.detail && (
        <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
          {errors.detail}
        </p>
      )}
      <DialogFooter className="items-center">
        <Button onClick={onDone}>{t("admin.boxes.adjust.cancel")}</Button>
        <Button type="submit" form={formId} variant="primary" disabled={save.isPending}>
          {t("admin.boxes.adjust.save")}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
