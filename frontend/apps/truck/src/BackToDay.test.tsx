import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { expect, test } from "vitest";

import { BackToDay } from "./BackToDay";

function markup(): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <BackToDay />
    </MemoryRouter>,
  );
}

test("the header's way back goes to Ma journée and says what it is", () => {
  expect(markup()).toContain('href="/"');
  expect(markup()).toContain('aria-label="Retour à Ma journée"');
});
