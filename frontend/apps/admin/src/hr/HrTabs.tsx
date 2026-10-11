import { useTranslation } from "@frutti/i18n";
import { cn } from "@frutti/ui";
import { NavLink } from "react-router";

/** Payroll month view and employees: the two lists of the "Personnel & salaires" module. */
export function HrTabs() {
  const { t } = useTranslation();
  const tabs = [
    { to: "/salaires", label: t("admin.hr.tabs.payroll"), end: true },
    { to: "/salaires/employes", label: t("admin.hr.tabs.employees"), end: false },
  ];
  return (
    <nav aria-label={t("admin.hr.tabs.label")} className="flex w-fit rounded-control bg-surface-2 p-1">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cn(
              "rounded-[7px] px-3 py-1.5 text-[0.85rem] font-semibold text-ink-2",
              isActive && "bg-surface text-ink shadow-card",
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
