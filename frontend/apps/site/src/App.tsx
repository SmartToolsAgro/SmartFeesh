import type { WebRequestKindEnum } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Sprite, Toaster, useFavicon } from "@frutti/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useSiteCatalog } from "./api";
import { addToCart, type CartLine, loadCart, saveCart } from "./cart";
import { CallButton } from "./Contact";
import { Header } from "./Header";
import { Hero } from "./Hero";
import { Products } from "./Products";
import { RequestForm } from "./RequestForm";
import { Footer, Marquee, Story, Values } from "./Sections";

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } });

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Sprite />
      <Site />
      <Toaster />
    </QueryClientProvider>
  );
}

function Site() {
  const { t } = useTranslation();
  const catalog = useSiteCatalog();
  const [cart, setCart] = useState<CartLine[]>(loadCart);
  const [kind, setKind] = useState<WebRequestKindEnum>("order");
  const [bump, setBump] = useState(0);

  useEffect(() => saveCart(cart), [cart]);
  // Products the site no longer shows (removed or hidden by the office since the last visit) are left out.
  const offered = catalog.data?.products;
  // The phone and details the office set in "Paramètres du site" (D-186); empty fields are not shown.
  const contact = catalog.data?.contact;
  // The company logo from the office app's Paramètres, also as the browser tab's icon.
  useFavicon(catalog.data?.logo_url);
  const shownCart = useMemo(() => {
    if (!offered) return cart;
    const ids = new Set(offered.map((product) => product.id));
    return cart.filter((line) => ids.has(line.product));
  }, [cart, offered]);

  const add = useCallback((product: number, quantity: string) => {
    setCart((lines) => addToCart(lines, product, quantity));
    setBump((count) => count + 1);
  }, []);
  const goToForm = useCallback((next: WebRequestKindEnum) => {
    setKind(next);
    document.getElementById("commande")?.scrollIntoView({ behavior: "smooth" });
  }, []);

  return (
    <>
      <a
        href="#produits"
        className="sr-only z-50 rounded-control bg-surface px-3 py-2 focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        {t("site.skip")}
      </a>
      <Header
        basketCount={shownCart.length}
        bump={bump}
        logoUrl={catalog.data?.logo_url}
        company={catalog.data?.company}
        phone={contact?.phone ?? ""}
        onBasket={() => goToForm("order")}
      />
      <main>
        <Hero
          phone={contact?.phone ?? ""}
          onOrder={() => document.getElementById("produits")?.scrollIntoView()}
          onQuote={() => goToForm("quote")}
        />
        <Marquee />
        <Values />
        <Products catalog={catalog} cart={shownCart} onAdd={add} />
        <Story />
        <RequestForm
          kind={kind}
          onKind={setKind}
          cart={cart}
          onCart={setCart}
          products={catalog.data?.products ?? []}
          phone={contact?.phone ?? ""}
        />
      </main>
      <Footer company={catalog.data?.company} logoUrl={catalog.data?.logo_url} contact={contact} />
      <CallButton contact={contact} />
    </>
  );
}
