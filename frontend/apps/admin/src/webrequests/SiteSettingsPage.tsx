import { getGetSiteSettingsQueryKey, saveSiteSettings, type SiteSettings, useGetSiteSettings } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { Button, Card, CardTitle, Field, Input, PageHeader, toast } from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useOutletContext } from "react-router";

import { fieldErrors } from "../lib/errors";
import { canRecordReceipts } from "../receipts/shared";
import { SITE_URL } from "./shared";

const FIELDS = ["phone", "whatsapp", "email", "address", "opening_hours"] as const;
type FieldName = (typeof FIELDS)[number];

/** The phone and contact details the public site shows (D-186). */
export function SiteSettingsPage() {
  const { t } = useTranslation();
  const settings = useGetSiteSettings();

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.site")} title={t("admin.siteSettings.title")}>
        <a
          href={SITE_URL}
          target="_blank"
          rel="noreferrer"
          className="text-[0.9rem] font-semibold text-sea hover:underline"
        >
          {t("admin.siteProducts.openSite")} ↗
        </a>
      </PageHeader>
      <p className="text-ink-2">{t("admin.siteSettings.intro")}</p>
      {settings.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : settings.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : (
        // Keyed on the saved values, so the form starts again from what the server wrote ("+216 74 123 456").
        <SettingsForm key={JSON.stringify(settings.data)} saved={settings.data} />
      )}
    </>
  );
}

function SettingsForm({ saved }: { saved: SiteSettings }) {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const canEdit = canRecordReceipts(session);
  const queryClient = useQueryClient();
  const formId = useId();
  const id = (name: FieldName) => `${formId}-${name}`;
  const [values, setValues] = useState<Record<FieldName, string>>({
    phone: saved.phone ?? "",
    whatsapp: saved.whatsapp ?? "",
    email: saved.email ?? "",
    address: saved.address ?? "",
    opening_hours: saved.opening_hours ?? "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const dirty = FIELDS.some((name) => values[name] !== (saved[name] ?? ""));

  const save = useMutation({
    mutationFn: () => saveSiteSettings(values),
    onSuccess: (answer) => {
      setErrors({});
      toast.success(t("admin.siteSettings.saved"));
      queryClient.setQueryData(getGetSiteSettingsQueryKey(), answer);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("common.serverUnreachable") });
    },
  });

  const field = (
    name: FieldName,
    props: { type?: string; inputMode?: "tel"; maxLength?: number; placeholder?: string },
  ) => (
    <Input
      id={id(name)}
      value={values[name]}
      readOnly={!canEdit}
      aria-invalid={errors[name] ? true : undefined}
      onChange={(event) => setValues((current) => ({ ...current, [name]: event.target.value }))}
      {...props}
    />
  );

  return (
    <Card className="max-w-2xl">
      <CardTitle>{t("admin.siteSettings.contact")}</CardTitle>
      {!canEdit && <p className="mb-3 text-[0.9rem] text-ink-2">{t("admin.siteSettings.readOnly")}</p>}
      <form
        noValidate
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (canEdit) save.mutate();
        }}
      >
        <Field label={t("admin.siteSettings.phone")} htmlFor={id("phone")} error={errors.phone}>
          {field("phone", { type: "tel", inputMode: "tel", maxLength: 30, placeholder: "74 123 456" })}
          {!errors.phone && (
            <span className="text-[0.78rem] text-ink-2">
              {values.phone.trim() ? t("admin.siteSettings.phoneHint") : t("admin.siteSettings.noPhone")}
            </span>
          )}
        </Field>
        <Field label={t("admin.siteSettings.whatsapp")} htmlFor={id("whatsapp")} error={errors.whatsapp}>
          {field("whatsapp", { type: "tel", inputMode: "tel", maxLength: 30 })}
          {!errors.whatsapp && (
            <span className="text-[0.78rem] text-ink-2">{t("admin.siteSettings.whatsappHint")}</span>
          )}
        </Field>
        <Field label={t("admin.siteSettings.email")} htmlFor={id("email")} error={errors.email}>
          {field("email", { type: "email" })}
        </Field>
        <Field label={t("admin.siteSettings.hours")} htmlFor={id("opening_hours")} error={errors.opening_hours}>
          {field("opening_hours", { maxLength: 200, placeholder: t("admin.siteSettings.hoursHint") })}
        </Field>
        <Field
          label={t("admin.siteSettings.postal")}
          htmlFor={id("address")}
          error={errors.address}
          className="sm:col-span-2"
        >
          {field("address", { maxLength: 250, placeholder: t("admin.siteSettings.postalHint") })}
        </Field>
        {errors.detail && (
          <p role="alert" className="text-[0.85rem] font-semibold text-bad sm:col-span-2">
            {errors.detail}
          </p>
        )}
        {canEdit && (
          <div className="sm:col-span-2">
            <Button type="submit" variant="primary" disabled={!dirty || save.isPending}>
              {t("admin.siteSettings.save")}
            </Button>
          </div>
        )}
      </form>
    </Card>
  );
}
