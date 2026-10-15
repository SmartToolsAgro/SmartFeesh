import { useEffect } from "react";

/**
 * Show the company logo from Paramètres as the browser-tab icon (D-125). Without a logo (or logged out) the
 * icon written in the app's `index.html` comes back.
 */
export function useFavicon(logoUrl: string | null | undefined): void {
  useEffect(() => {
    if (!logoUrl) return;
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]') ?? document.createElement("link");
    // No type is set: the logo may be a PNG, JPEG or WebP, and a wrong type can make the browser skip the icon.
    const previous = { href: link.getAttribute("href"), attached: link.isConnected };
    link.rel = "icon";
    link.href = logoUrl;
    if (!previous.attached) document.head.appendChild(link);
    return () => {
      if (!previous.attached) {
        link.remove();
        return;
      }
      if (previous.href === null) link.removeAttribute("href");
      else link.setAttribute("href", previous.href);
    };
  }, [logoUrl]);
}
