import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";

import { Combobox, type ComboboxOption } from "./combobox";

// jsdom has no layout: the popover's positioning needs these two to exist.
beforeAll(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  Element.prototype.scrollIntoView = () => {};
});

afterEach(cleanup);

const OPTIONS: ComboboxOption[] = [
  { value: "1", label: "Crevette royale · ART0002", keywords: ["Crustacés"] },
  { value: "2", label: "Sardine · SA-010", keywords: ["Poissons bleus"] },
  { value: "3", label: "Dorade royale · DO-003", keywords: ["Poissons blancs"] },
];

function Picker({ initial = "", onChosen }: { initial?: string; onChosen?: () => void }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <Combobox
        aria-label="Produit"
        value={value}
        onValueChange={setValue}
        options={OPTIONS}
        empty="Aucun produit trouvé."
        onChosen={onChosen}
      />
      <output>{value}</output>
      <button type="button">Ailleurs</button>
    </>
  );
}
const names = () => screen.getAllByRole("option").map((option) => option.getAttribute("aria-label"));

test("typing filters the list, by name, code or keyword, and Enter takes the first match", async () => {
  const user = userEvent.setup();
  const onChosen = vi.fn();
  render(<Picker onChosen={onChosen} />);
  const field = screen.getByRole("combobox", { name: "Produit" });
  expect(screen.queryByRole("listbox")).toBeNull();

  await user.type(field, "roy");
  expect(names()).toEqual(["Crevette royale · ART0002", "Dorade royale · DO-003"]);

  await user.clear(field);
  await user.type(field, "bleus");
  expect(names()).toEqual(["Sardine · SA-010"]);

  await user.clear(field);
  await user.type(field, "do003{Enter}");
  expect(screen.getByRole("status").textContent).toBe("3");
  expect((field as HTMLInputElement).value).toBe("Dorade royale · DO-003");
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(onChosen).toHaveBeenCalledTimes(1);
});

test("a click opens the whole list; the arrows and a click choose in it", async () => {
  const user = userEvent.setup();
  render(<Picker />);
  const field = screen.getByRole("combobox", { name: "Produit" });

  await user.click(field);
  expect(names()).toHaveLength(3);
  // Nothing is highlighted until an arrow is pressed: Enter alone takes nothing.
  await user.keyboard("{Enter}");
  expect(screen.getByRole("status").textContent).toBe("");
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
  expect(screen.getByRole("status").textContent).toBe("2");

  await user.click(field);
  await user.click(screen.getByRole("option", { name: "Crevette royale · ART0002" }));
  expect(screen.getByRole("status").textContent).toBe("1");
  expect((field as HTMLInputElement).value).toBe("Crevette royale · ART0002");
});

test("what is typed and matches nothing says so, and Escape gives the value back", async () => {
  const user = userEvent.setup();
  render(<Picker initial="2" />);
  const field = screen.getByRole("combobox", { name: "Produit" });

  await user.clear(field);
  await user.type(field, "thon");
  expect(screen.getByText("Aucun produit trouvé.")).toBeDefined();
  await user.keyboard("{Enter}");
  expect(screen.getByRole("status").textContent).toBe("2");

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("listbox")).toBeNull();
  expect((field as HTMLInputElement).value).toBe("Sardine · SA-010");
});

test("an option taken once the field was emptied stays, also when the focus moves on at once", async () => {
  const user = userEvent.setup();
  // A grid moves to its next cell as soon as an option is taken.
  render(<Picker initial="2" onChosen={() => screen.getByRole("button", { name: "Ailleurs" }).focus()} />);
  const field = screen.getByRole("combobox", { name: "Produit" });

  await user.clear(field);
  await user.click(screen.getByRole("option", { name: "Dorade royale · DO-003" }));

  expect(screen.getByRole("status").textContent).toBe("3");
  expect((field as HTMLInputElement).value).toBe("Dorade royale · DO-003");
});

test("leaving the field emptied removes the value; leaving it half typed keeps the value", async () => {
  const user = userEvent.setup();
  render(<Picker initial="2" />);
  const field = screen.getByRole("combobox", { name: "Produit" });

  await user.clear(field);
  await user.type(field, "zzz");
  await user.click(screen.getByRole("button", { name: "Ailleurs" }));
  expect(screen.getByRole("status").textContent).toBe("2");
  expect((field as HTMLInputElement).value).toBe("Sardine · SA-010");

  await user.clear(field);
  await user.click(screen.getByRole("button", { name: "Ailleurs" }));
  expect(screen.getByRole("status").textContent).toBe("");
  expect((field as HTMLInputElement).value).toBe("");
});
