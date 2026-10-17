import { useTranslation } from "@frutti/i18n";
import { Popover as PopoverPrimitive } from "radix-ui";
import { useState } from "react";

import { Icon } from "../icons";
import { cn } from "../lib/cn";

export interface BellItem {
  id: number;
  text: string;
  /** When it happened, already formatted. */
  time: string;
  read: boolean;
}

interface Props {
  items: BellItem[];
  unread: number;
  /** A click on one notification: mark it read and go where it says. */
  onOpen: (id: number) => void;
  onReadAll: () => void;
  soundOn: boolean;
  onToggleSound: () => void;
  /** "dark" on the driver's blue header, "light" on the office's white bar. */
  tone?: "light" | "dark";
}

/** The bell of the header (D-175): the count of unread notifications, and the list under it. */
export function NotificationBell({ items, unread, onOpen, onReadAll, soundOn, onToggleSound, tone = "light" }: Props) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const label = unread > 0 ? t("notifications.openUnread", { count: unread }) : t("notifications.open");
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger
        aria-label={label}
        title={label}
        className={cn(
          "relative grid size-9 flex-none place-items-center rounded-full",
          tone === "dark" ? "bg-white/15 text-white" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
        )}
      >
        <Icon name="bell" className="size-[19px]" />
        {unread > 0 && (
          <span className="absolute -end-0.5 -top-0.5 min-w-[18px] rounded-full bg-coral px-[5px] text-center text-[0.68rem] leading-[18px] font-bold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="end"
          sideOffset={8}
          collisionPadding={12}
          className="z-50 flex max-h-[min(480px,calc(100dvh-90px))] w-[min(380px,calc(100vw-24px))] flex-col overflow-hidden rounded-card border border-line bg-surface text-ink shadow-card"
        >
          <div className="flex items-center gap-2 border-b border-line px-4 py-3">
            <h3 className="flex-1 text-[1rem]">{t("notifications.title")}</h3>
            <button
              type="button"
              onClick={onToggleSound}
              aria-pressed={soundOn}
              className="rounded-full px-2.5 py-1 text-[0.78rem] font-semibold text-ink-2 hover:bg-surface-2"
            >
              {soundOn ? t("notifications.soundOn") : t("notifications.soundOff")}
            </button>
            {unread > 0 && (
              <button
                type="button"
                onClick={onReadAll}
                className="rounded-full px-2.5 py-1 text-[0.78rem] font-semibold text-sea hover:bg-sea-soft"
              >
                {t("notifications.readAll")}
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-center text-ink-2">{t("notifications.empty")}</p>
          ) : (
            <ul className="overflow-y-auto overscroll-contain">
              {items.map((item) => (
                <li key={item.id} className="border-b border-line last:border-b-0">
                  <button
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      onOpen(item.id);
                    }}
                    className={cn(
                      "flex w-full items-start gap-2.5 px-4 py-3 text-start hover:bg-surface-2",
                      !item.read && "bg-sea-soft/60",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "mt-[7px] size-2 flex-none rounded-full",
                        item.read ? "bg-transparent" : "bg-coral",
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span className={cn("block text-[0.9rem]", !item.read && "font-semibold")}>{item.text}</span>
                      <span className="block text-[0.75rem] text-ink-2">{item.time}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
