import type { ReactNode } from "react";

/** The screen's main action stays on screen while the long form above it scrolls (D-171). */
export function StickyAction({ children }: { children: ReactNode }) {
  return (
    <div className="sticky bottom-0 z-10 -mx-3.5 space-y-2 border-t border-line bg-bg/95 p-3.5 backdrop-blur">
      {children}
    </div>
  );
}
