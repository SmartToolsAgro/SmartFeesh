import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { expect, test } from "vitest";

import { BackToDay } from "./BackToDay";

function markup(pathname: string): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[pathname]}>
      <BackToDay pathname={pathname} />
    </MemoryRouter>,
  );
}

test("every driver screen but Ma journée has a Retour button to Ma journée", () => {
  for (const pathname of ["/cloture", "/stock", "/vente", "/depense", "/encaissement", "/perte", "/reprise"]) {
    expect(markup(pathname), pathname).toContain('href="/"');
    expect(markup(pathname), pathname).toContain("Retour à Ma journée");
  }
});

test("Ma journée itself has no such button", () => {
  expect(markup("/")).toBe("");
});
