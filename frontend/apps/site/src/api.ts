// The two calls of the public site. Through the shared transport only: importing the whole generated client
// (with every Zod schema of the office apps) would make the visitors' download several times bigger.
import type { SiteCatalog, SiteRequest, SiteRequestReceived } from "@frutti/api";
import { apiFetch } from "@frutti/api/src/http";
import { useQuery } from "@tanstack/react-query";

export { ApiError } from "@frutti/api/src/http";

export function useSiteCatalog() {
  return useQuery({
    queryKey: ["/api/v1/site/catalog"],
    queryFn: ({ signal }) => apiFetch<SiteCatalog>("/api/v1/site/catalog", { signal }),
    staleTime: 5 * 60_000,
    retry: 1,
  });
}

export function sendSiteRequest(body: SiteRequest): Promise<SiteRequestReceived> {
  return apiFetch<SiteRequestReceived>("/api/v1/site/requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
