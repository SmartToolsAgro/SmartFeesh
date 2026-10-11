import { useTranslation } from "@frutti/i18n";
import { EmptyState, PageHeader } from "@frutti/ui";

/** What a manager sees instead of the pay screens: the server answers 403 to them too (D-055). */
export function PayRestricted() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader eyebrow={t("admin.groups.finance")} title={t("admin.nav.payroll")} />
      <EmptyState illustration="fridge" title={t("admin.hr.restricted")}>
        {t("admin.hr.restrictedBody")}
      </EmptyState>
    </>
  );
}
