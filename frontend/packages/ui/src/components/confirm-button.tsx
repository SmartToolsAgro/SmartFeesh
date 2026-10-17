import { useTranslation } from "@frutti/i18n";
import { type ReactNode, useState } from "react";

import { Button, type ButtonProps } from "./button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogTitle } from "./dialog";

type ConfirmButtonProps = Omit<ButtonProps, "onClick" | "asChild" | "title"> & {
  /** Runs only after "Confirmer"; "Annuler" closes the window and does nothing. */
  onConfirm: () => void;
  title?: ReactNode;
  /** What is about to be recorded, as label / amount rows the user checks before it is sent. */
  rows?: [ReactNode, ReactNode][];
};

/** A button that asks "Annuler / Confirmer" before it acts. Every action that records money uses it (D-179). */
export function ConfirmButton({ onConfirm, title, rows = [], children, ...props }: ConfirmButtonProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button {...props} onClick={() => setOpen(true)}>
        {children}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>{title ?? t("common.confirmTitle")}</DialogTitle>
          <DialogDescription asChild>
            <dl className="space-y-1">
              {rows.map(([label, value], index) => (
                <div key={index} className="flex items-baseline justify-between gap-3">
                  <dt>{label}</dt>
                  <dd className="text-lg font-bold text-ink">{value}</dd>
                </div>
              ))}
            </dl>
          </DialogDescription>
          <DialogFooter className="grid grid-cols-2">
            <DialogClose asChild>
              <Button size="lg">{t("common.cancel")}</Button>
            </DialogClose>
            <Button
              size="lg"
              variant="primary"
              onClick={() => {
                setOpen(false);
                onConfirm();
              }}
            >
              {t("common.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
