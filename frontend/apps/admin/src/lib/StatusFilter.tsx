import { cn } from "@frutti/ui";

const STATUSES = ["active", "archived", "all"] as const;
export type Status = (typeof STATUSES)[number];

/** Active / archived / all, as pressed buttons. `labels` gives the text of each choice. */
export function StatusFilter({
  value,
  onChange,
  label,
  labels,
}: {
  value: Status;
  onChange: (status: Status) => void;
  label: string;
  labels: Record<Status, string>;
}) {
  return (
    <div role="group" aria-label={label} className="flex rounded-control bg-surface-2 p-1">
      {STATUSES.map((status) => (
        <button
          key={status}
          type="button"
          aria-pressed={value === status}
          onClick={() => onChange(status)}
          className={cn(
            "rounded-[7px] px-3 py-1.5 text-[0.85rem] font-semibold text-ink-2",
            value === status && "bg-surface text-ink shadow-card",
          )}
        >
          {labels[status]}
        </button>
      ))}
    </div>
  );
}
