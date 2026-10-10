import { Toaster as Sonner } from "sonner";

/** Mount once per app. Then call `toast("Vente enregistrée")` or `toast.error(...)` from anywhere. */
export function Toaster({ position = "bottom-center" }: { position?: "bottom-center" | "bottom-right" }) {
  return (
    <Sonner
      position={position}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "flex w-full items-center gap-2.5 rounded-xl bg-ink px-3.5 py-3 text-[0.88rem] font-semibold text-surface shadow-card",
          error: "bg-bad text-white",
        },
      }}
    />
  );
}
