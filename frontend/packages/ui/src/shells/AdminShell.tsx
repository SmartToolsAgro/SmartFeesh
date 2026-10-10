import { useTranslation } from "@frutti/i18n";
import type { ReactNode } from "react";
import { NavLink } from "react-router";

import { Button } from "../components/button";
import { Pill } from "../components/pill";
import type { IconName } from "../icon-names";
import { Icon } from "../icons";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

export interface AdminNavGroup {
  label: string;
  items: { to: string; label: string; icon: IconName; badge?: string }[];
}

interface Props {
  nav: AdminNavGroup[];
  user: { name: string; role: string };
  onLogout: () => void;
  children: ReactNode;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

/** Back-office frame: sticky top bar, module sidebar (a scrolling strip on small screens), page area. */
export function AdminShell({ nav, user, onLogout, children }: Props) {
  const { t } = useTranslation();
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 flex flex-wrap items-center gap-4 border-b border-line bg-surface/90 px-5 py-3 backdrop-blur-md max-sm:gap-2.5 max-sm:px-4 max-sm:py-2.5">
        <Brand />
        <div className="flex-1" />
        <ThemeToggle />
        <div className="flex items-center gap-2.5">
          <div className="grid size-[30px] flex-none place-items-center rounded-full bg-sea-soft text-[0.75rem] font-bold text-sea">
            {initials(user.name)}
          </div>
          <div className="leading-tight max-sm:hidden">
            <div className="font-semibold">{user.name}</div>
            <Pill tone="sea" className="px-[7px] py-px text-[0.68rem]">
              {user.role}
            </Pill>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("common.logout")}
            title={t("common.logout")}
            onClick={onLogout}
          >
            <Icon name="return" />
          </Button>
        </div>
      </header>

      <div className="grid min-h-[calc(100dvh-62px)] grid-cols-[232px_minmax(0,1fr)] max-[860px]:grid-cols-1">
        <nav
          aria-label={t("admin.modules")}
          className="flex flex-col gap-0.5 border-e border-line bg-surface px-3 py-[18px] max-[860px]:flex-row max-[860px]:gap-1.5 max-[860px]:overflow-x-auto max-[860px]:border-e-0 max-[860px]:border-b max-[860px]:px-4 max-[860px]:py-2.5"
        >
          {nav.map((group) => (
            <div key={group.label} className="contents">
              <div className="eyebrow mx-2.5 mt-3.5 mb-1.5 max-[860px]:hidden">{group.label}</div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className="flex flex-none items-center gap-[11px] rounded-[10px] px-3 py-[9px] font-medium whitespace-nowrap text-ink-2 hover:bg-surface-2 hover:text-ink aria-[current=page]:bg-sea-soft aria-[current=page]:font-bold aria-[current=page]:text-sea"
                >
                  <Icon name={item.icon} />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ms-auto rounded-full bg-coral px-[7px] py-px text-[0.68rem] font-bold text-white">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <main className="flex min-w-0 flex-col gap-[22px] px-8 pt-7 pb-12 max-[860px]:px-4 max-[860px]:pt-5 max-[860px]:pb-10">
          {children}
        </main>
      </div>
    </div>
  );
}

/** Title row of a page: eyebrow, heading, and the page's actions on the right. */
export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
      </div>
      <div className="min-w-2 flex-1" />
      {children}
    </div>
  );
}
