import type { WebRequestKindEnum, WebRequestStatusEnum } from "@frutti/api";

export const STATUS_TONE: Record<WebRequestStatusEnum, "coral" | "good" | "neutral"> = {
  new: "coral",
  handled: "good",
  cancelled: "neutral",
};

export const KIND_TONE: Record<WebRequestKindEnum, "sea" | "warn"> = {
  quote: "sea",
  order: "warn",
};

/** The public site's address (D-186): the "Voir le site" links of the "Site web" screens. */
export const SITE_URL = "https://www.fruttidelmare.com";
