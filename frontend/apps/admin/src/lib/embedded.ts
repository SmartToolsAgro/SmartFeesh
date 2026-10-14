import { createContext, useContext } from "react";
import { useNavigate } from "react-router";

/** Set while a creation form is shown in a window on the Documents page (D-137), not as a page of its own. */
export const EmbeddedContext = createContext<{ close: () => void } | null>(null);

/**
 * Where a form goes once it is saved or cancelled: its own page, or, inside a window, the window closes and the
 * person stays on the list.
 */
export function useLeave() {
  const navigate = useNavigate();
  const embedded = useContext(EmbeddedContext);
  return {
    embedded: embedded !== null,
    leave: (to: string) => {
      if (embedded) embedded.close();
      else void navigate(to);
    },
  };
}
