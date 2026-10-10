import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

const pillVariants = cva(
  "inline-flex items-center gap-[5px] rounded-full px-[9px] py-[3px] text-[0.75rem] font-bold whitespace-nowrap",
  {
    variants: {
      tone: {
        good: "bg-good-soft text-good",
        warn: "bg-warn-soft text-warn",
        bad: "bg-bad-soft text-bad",
        sea: "bg-sea-soft text-sea",
        coral: "bg-coral-soft text-coral",
        neutral: "bg-surface-2 text-ink-2",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

/** A small status label. The tone carries meaning: never use it as decoration. */
export function Pill({ className, tone, ...props }: ComponentProps<"span"> & VariantProps<typeof pillVariants>) {
  return <span className={cn(pillVariants({ tone }), className)} {...props} />;
}
