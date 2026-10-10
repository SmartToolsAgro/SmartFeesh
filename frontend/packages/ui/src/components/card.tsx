import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div className={cn("min-w-0 rounded-card border border-line bg-surface p-5 shadow-card", className)} {...props} />
  );
}

export function CardTitle({ className, ...props }: ComponentProps<"h2">) {
  return <h2 className={cn("mb-3", className)} {...props} />;
}
