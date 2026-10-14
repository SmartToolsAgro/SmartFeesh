import { Popover } from "radix-ui";
import { type ComponentProps, type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";

import { cn } from "../lib/cn";
import { type Searchable, searchOptions } from "../lib/search";
import { controlClasses } from "./input";

export type ComboboxOption = Searchable & {
  value: string;
  /** A richer drawing of the option in the list; its label when missing. */
  detail?: ReactNode;
};

type ComboboxProps = Omit<ComponentProps<"input">, "value" | "onChange" | "role"> & {
  /** The chosen option's value; empty for none. */
  value: string;
  onValueChange: (value: string) => void;
  options: ComboboxOption[];
  /** Said in the list when nothing matches what is typed. */
  empty: string;
  /** Called once an option is taken with Enter or a click: a grid moves on to its next cell. */
  onChosen?: () => void;
  /** Up and down open the list (the default). A grid turns this off to keep the arrows for its rows. */
  arrowsOpen?: boolean;
  /** No border or background of its own: the cell of a grid draws them. */
  plain?: boolean;
};

const keep = (event: { preventDefault: () => void }) => event.preventDefault();

/**
 * A field to type in, with the choices that match listed under it: found by their label or their keywords
 * (`searchOptions`). Enter or a click takes a choice; leaving the field emptied removes it.
 */
export function Combobox({
  value,
  onValueChange,
  options,
  empty,
  onChosen,
  arrowsOpen = true,
  plain = false,
  className,
  onFocus,
  onBlur,
  onClick,
  onKeyDown,
  ...props
}: ComboboxProps) {
  const listId = useId();
  const field = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  // What is being typed; null while the field shows its value. `typed` holds the same for the blur that
  // comes before the next render, when taking an option moves the focus on at once.
  const [query, setQuery] = useState<string | null>(null);
  const typed = useRef<string | null>(null);
  const type = (text: string | null) => {
    typed.current = text;
    setQuery(text);
  };
  const [open, setOpen] = useState(false);
  // The option Enter takes; -1 for none, until something is typed or an arrow is pressed.
  const [active, setActive] = useState(-1);

  const chosen = options.find((option) => option.value === value);
  const matches = query === null ? options : searchOptions(options, query);
  const current = open ? matches[active] : undefined;

  useEffect(() => {
    if (open) list.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  function show() {
    setActive(matches.findIndex((option) => option.value === value));
    setOpen(true);
  }

  function take(option: ComboboxOption) {
    onValueChange(option.value);
    type(null);
    setOpen(false);
  }

  function onKey(event: KeyboardEvent<HTMLInputElement>) {
    onKeyDown?.(event);
    const down = event.key === "ArrowDown";
    if (down || event.key === "ArrowUp") {
      if (open) {
        const count = matches.length;
        if (count > 0) setActive((index) => (down ? (index + 1) % count : (Math.max(index, 0) + count - 1) % count));
      } else if (arrowsOpen || event.altKey) show();
      else return;
      event.preventDefault();
      event.stopPropagation();
    } else if (event.key === "Enter" && open) {
      // Never the form's Enter while the list is open, also when nothing matches.
      event.preventDefault();
      event.stopPropagation();
      if (current) {
        take(current);
        onChosen?.();
      }
    } else if (event.key === "Tab" && current && query !== null && query.trim() !== "") {
      take(current);
    } else if (event.key === "Escape" && (open || query !== null)) {
      // The popover has closed itself already; what was typed goes too, and an enclosing dialog stays open.
      event.stopPropagation();
      type(null);
      setOpen(false);
    }
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Anchor asChild>
        <input
          {...props}
          ref={field}
          role="combobox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-autocomplete="list"
          aria-activedescendant={current ? `${listId}-${active}` : undefined}
          autoComplete="off"
          value={query ?? chosen?.label ?? ""}
          onChange={(event) => {
            type(event.target.value);
            setActive(event.target.value.trim() === "" ? -1 : 0);
            setOpen(true);
          }}
          onFocus={(event) => {
            event.currentTarget.select();
            onFocus?.(event);
          }}
          onBlur={(event) => {
            setOpen(false);
            if (typed.current !== null && typed.current.trim() === "" && value !== "") onValueChange("");
            type(null);
            onBlur?.(event);
          }}
          onClick={(event) => {
            if (!open) show();
            onClick?.(event);
          }}
          onKeyDown={onKey}
          className={cn(!plain && controlClasses, className)}
        />
      </Popover.Anchor>
      <Popover.Portal>
        <Popover.Content
          ref={list}
          id={listId}
          role="listbox"
          align="start"
          sideOffset={4}
          collisionPadding={8}
          // The field keeps the focus: the list is only pointed at, or walked with the arrows.
          onOpenAutoFocus={keep}
          onCloseAutoFocus={keep}
          onFocusOutside={keep}
          onPointerDownOutside={(event) => {
            if (event.target === field.current) event.preventDefault();
          }}
          onMouseDown={keep}
          className="z-50 max-h-72 max-w-[calc(100vw-1rem)] min-w-(--radix-popover-trigger-width) overflow-y-auto rounded-control border border-line bg-surface p-1 shadow-card"
        >
          {matches.length === 0 && (
            <p role="presentation" className="px-2.5 py-2 text-[0.9rem] text-ink-2">
              {empty}
            </p>
          )}
          {matches.map((option, index) => (
            <div
              key={option.value}
              id={`${listId}-${index}`}
              role="option"
              aria-label={option.label}
              aria-selected={index === active}
              onMouseMove={() => {
                if (index !== active) setActive(index);
              }}
              onClick={() => {
                take(option);
                onChosen?.();
              }}
              className={cn(
                "cursor-pointer rounded-[7px] px-2.5 py-2 text-[0.9rem] select-none",
                index === active && "bg-sea-soft text-sea",
              )}
            >
              {option.detail ?? option.label}
            </div>
          ))}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
