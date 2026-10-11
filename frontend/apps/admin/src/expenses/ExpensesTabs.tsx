import { useTranslation } from "@frutti/i18n";
import { cn } from "@frutti/ui";
import { NavLink } from "react-router";

// The sections of the "Charges" entry of the menu: expenses, the day-labour calendar and the labourers.
const TABS = [
  { to: "/charges", label: "admin.expenseTabs.expenses", end: true },
  { to: "/charges/calendrier", label: "admin.expenseTabs.calendar", end: false },
  { to: "/charges/journaliers", label: "admin.expenseTabs.labourers", end: false },
  { to: "/charges/froid", label: "admin.expenseTabs.coldRooms", end: false },
  { to: "/charges/frais-generaux", label: "admin.expenseTabs.general", end: false },
] as const;

/** Links between the sections of the expenses module, the current one marked. */
export function ExpensesTabs() {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("admin.expenseTabs.label")} className="flex flex-wrap gap-1 border-b border-line">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            cn(
              "-mb-px border-b-2 border-transparent px-3 py-2 text-[0.9rem] font-semibold text-ink-2 hover:text-ink",
              isActive && "border-coral text-ink",
            )
          }
        >
          {t(tab.label)}
        </NavLink>
      ))}
    </nav>
  );
}
