import {
  acceptQuote,
  cancelPurchaseOrder,
  cancelSale,
  closePurchaseOrder,
  confirmSale,
  createInvoice,
  deleteInvoice,
  deleteSupplierInvoice,
  type DocumentRow,
  issueInvoice,
  postSupplierInvoice,
  refuseQuote,
  sendQuote,
} from "@frutti/api";

/** The actions the server may offer on a row (`DocumentRow.actions`, D-102). */
export type DocumentAction =
  | "edit"
  | "send"
  | "accept"
  | "refuse"
  | "to_sale"
  | "confirm"
  | "cancel"
  | "to_invoice"
  | "issue"
  | "delete"
  | "credit_note"
  | "receive"
  | "close"
  | "to_supplier_invoice"
  | "post"
  | "pay";

/** What happens on a click: open another page, or ask first and then call the API from this page. */
export type ActionPlan =
  | { kind: "page"; to: string }
  | { kind: "ask"; reason: "none" | "optional" | "required"; run: (reason: string) => Promise<RunResult> }
  | { kind: "to_sale" };

/** What a finished action tells the page: the number to name in the message, and a page to open next. */
export interface RunResult {
  number?: string;
  open?: string;
  // A BL above the customer's credit limit stays a draft until the owner or manager approves it (D-062).
  pendingCredit?: boolean;
}

// The main action of each state, shown as a coloured button; the others are plain.
const MAIN: ReadonlySet<DocumentAction> = new Set([
  "send",
  "accept",
  "to_sale",
  "confirm",
  "to_invoice",
  "issue",
  "receive",
  "to_supplier_invoice",
  "post",
]);
// Actions that undo or remove something: shown in red.
const DANGER: ReadonlySet<DocumentAction> = new Set(["cancel", "delete", "refuse"]);

export const isMain = (action: DocumentAction) => MAIN.has(action);
export const isDanger = (action: DocumentAction) => DANGER.has(action);

/** How to carry out `action` on `row`. Each call goes to the endpoint of the app that owns the document. */
export function planOf(row: DocumentRow, action: DocumentAction): ActionPlan | null {
  const { id } = row;
  switch (`${row.type}.${action}`) {
    case "DV.edit":
      return { kind: "page", to: `/devis/${id}/modifier` };
    case "DV.send":
      return { kind: "ask", reason: "none", run: async () => ({ number: (await sendQuote(id)).number }) };
    case "DV.accept":
      return { kind: "ask", reason: "none", run: async () => ({ number: (await acceptQuote(id)).number }) };
    case "DV.refuse":
      return {
        kind: "ask",
        reason: "optional",
        run: async (reason) => ({ number: (await refuseQuote(id, { reason })).number }),
      };
    case "DV.to_sale":
      return { kind: "to_sale" };
    case "BL.edit":
      return { kind: "page", to: `/ventes/${id}/modifier` };
    case "BL.confirm":
      return {
        kind: "ask",
        reason: "none",
        run: async () => {
          const saved = await confirmSale(id, { approve_credit: false });
          return { number: saved.number, pendingCredit: saved.status === "draft" };
        },
      };
    case "BL.cancel":
      return {
        kind: "ask",
        // A validated BL brings its kilos back: the services want to know why (a draft simply stops).
        reason: row.status === "confirmed" ? "required" : "optional",
        run: async (reason) => ({ number: (await cancelSale(id, { reason })).number }),
      };
    case "BL.to_invoice":
      return {
        kind: "ask",
        reason: "none",
        run: async () => ({ open: `/factures/${(await createInvoice({ sale: id })).id}` }),
      };
    case "FA.edit":
      return { kind: "page", to: `/factures/${id}` };
    case "FA.issue":
      return { kind: "ask", reason: "none", run: async () => ({ number: (await issueInvoice(id)).number }) };
    case "FA.delete":
      return {
        kind: "ask",
        reason: "none",
        run: async () => {
          await deleteInvoice(id);
          return {};
        },
      };
    case "FA.credit_note":
      // The credit note dialog (lines, kilos back to stock or loss) lives on the invoice page.
      return { kind: "page", to: `/factures/${id}` };
    case "BA.receive":
      return { kind: "page", to: `/achats/nouvelle?commande=${id}` };
    case "BA.cancel":
      return { kind: "ask", reason: "none", run: async () => ({ number: (await cancelPurchaseOrder(id)).number }) };
    case "BA.close":
      return { kind: "ask", reason: "none", run: async () => ({ number: (await closePurchaseOrder(id)).number }) };
    case "BR.to_supplier_invoice":
      return { kind: "page", to: `/achats/factures/nouvelle?fournisseur=${row.partner_id}&reception=${id}` };
    case "FF.edit":
      return { kind: "page", to: `/achats/factures/${id}/modifier` };
    case "FF.post":
      return { kind: "ask", reason: "none", run: async () => ({ number: (await postSupplierInvoice(id)).number }) };
    case "FF.delete":
      return {
        kind: "ask",
        reason: "none",
        run: async () => {
          await deleteSupplierInvoice(id);
          return {};
        },
      };
    case "FF.pay":
      return { kind: "page", to: `/achats/paiements/nouveau?fournisseur=${row.partner_id}&facture=${id}` };
    default:
      return null;
  }
}
