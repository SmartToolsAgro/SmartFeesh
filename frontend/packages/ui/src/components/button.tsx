import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "../lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-control border font-semibold whitespace-nowrap transition-[filter,background-color] disabled:opacity-50 [&_svg]:size-[17px]",
  {
    variants: {
      variant: {
        // Coral is reserved for the main action of a screen.
        primary: "border-coral bg-coral text-white hover:brightness-105",
        secondary: "border-line bg-surface text-ink hover:bg-surface-2",
        ghost: "border-transparent bg-transparent text-ink-2 hover:bg-surface-2 hover:text-ink",
        danger: "border-bad bg-bad text-white hover:brightness-105",
      },
      size: {
        md: "px-[15px] py-[9px] text-[0.9rem]",
        // Phone-sized: a full-width, thumb-friendly button.
        lg: "w-full px-4 py-[13px] text-[0.95rem]",
        icon: "size-9 p-0",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

type ButtonProps = ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean };

/** `asChild` styles the child element instead (a link that looks like a button). */
export function Button({ className, variant, size, asChild = false, type, ...props }: ButtonProps) {
  const Component = asChild ? Slot.Root : "button";
  return (
    <Component
      className={cn(buttonVariants({ variant, size }), className)}
      {...(asChild ? {} : { type: type ?? "button" })}
      {...props}
    />
  );
}
