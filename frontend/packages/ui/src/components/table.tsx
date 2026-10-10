import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

/** Wraps the table so a wide one scrolls inside its card instead of stretching the page. */
export function Table({ className, ...props }: ComponentProps<"table">) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full border-collapse text-[0.9rem]", className)} {...props} />
    </div>
  );
}

export function Th({ className, numeric = false, ...props }: ComponentProps<"th"> & { numeric?: boolean }) {
  return (
    <th
      className={cn(
        "border-b border-line px-2.5 py-2 text-[0.72rem] font-semibold tracking-[0.07em] text-ink-2 uppercase",
        numeric ? "text-end" : "text-start",
        className,
      )}
      {...props}
    />
  );
}

/** `numeric` aligns to the end of the line and uses fixed-width digits: use it for every amount and weight. */
export function Td({ className, numeric = false, ...props }: ComponentProps<"td"> & { numeric?: boolean }) {
  return (
    <td
      className={cn(
        "border-b border-line px-2.5 py-[11px] align-middle [tr:last-child>&]:border-b-0",
        numeric && "num text-end",
        className,
      )}
      {...props}
    />
  );
}
