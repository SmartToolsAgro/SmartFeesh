import type { ComponentProps, ReactNode } from "react";

import { cn } from "../lib/cn";

export const controlClasses =
  "w-full rounded-control border border-line bg-surface px-3 py-2.5 text-ink placeholder:text-ink-2/70 disabled:opacity-50 aria-invalid:border-bad";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(controlClasses, className)} {...props} />;
}

export function Label({ className, ...props }: ComponentProps<"label">) {
  return <label className={cn("text-[0.78rem] font-semibold text-ink-2", className)} {...props} />;
}

/** A label above its control, with an optional error line below. */
export function Field({
  label,
  htmlFor,
  error,
  className,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-[5px]", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error && <p className="text-[0.78rem] font-semibold text-bad">{error}</p>}
    </div>
  );
}
