import type { ReactNode } from "react";

/** A card that opens on tap: its title and one summary line stay in view, so the screen is shorter (D-171). */
export function FoldCard({
  title,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details open={defaultOpen} className="group rounded-card border border-line bg-surface shadow-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-4 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          <span className="block text-lg font-bold">{title}</span>
          {summary ? <span className="block text-sm text-ink-2">{summary}</span> : null}
        </span>
        <span
          aria-hidden="true"
          className="size-2.5 flex-none rotate-45 border-b-2 border-r-2 border-ink-2 transition-transform group-open:rotate-[225deg]"
        />
      </summary>
      <div className="px-4 pb-4">{children}</div>
    </details>
  );
}
