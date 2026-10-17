import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Button } from "./components/button";
import { useFavicon } from "./favicon";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./components/dialog";
import { NotificationBell } from "./components/notification-bell";
import { Pill } from "./components/pill";
import { ICON_NAMES, ILLUSTRATION_NAMES } from "./icon-names";
import { Icon, Sprite } from "./icons";
import { Brand } from "./shells/Brand";
import { ThemeToggle } from "./shells/ThemeToggle";
import { initTheme } from "./theme";

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

afterEach(cleanup);

test("every icon and illustration name has a drawing in the sprite", () => {
  const { container } = render(<Sprite />);

  for (const name of ICON_NAMES) expect(container.querySelector(`symbol#i-${name}`), name).not.toBeNull();
  for (const name of ILLUSTRATION_NAMES) expect(container.querySelector(`symbol#p-${name}`), name).not.toBeNull();
});

test("an icon is decorative unless it is given a label", () => {
  const { container } = render(
    <>
      <Icon name="truck" />
      <Icon name="alert" aria-label="Attention" />
    </>,
  );

  const [decorative, labelled] = container.querySelectorAll("svg");
  expect(decorative?.getAttribute("aria-hidden")).toBe("true");
  expect(decorative?.querySelector("use")?.getAttribute("href")).toBe("#i-truck");
  expect(labelled?.hasAttribute("aria-hidden")).toBe(false);
});

test("a button does not submit a form unless asked to, and a pill carries its tone", () => {
  render(
    <>
      <Button>Annuler</Button>
      <Button type="submit" variant="primary">
        Valider
      </Button>
      <Pill tone="good">Payé</Pill>
    </>,
  );

  expect(screen.getByRole("button", { name: "Annuler" }).getAttribute("type")).toBe("button");
  expect(screen.getByRole("button", { name: "Valider" }).getAttribute("type")).toBe("submit");
  expect(screen.getByRole("button", { name: "Valider" }).className).toContain("bg-coral");
  expect(screen.getByText("Payé").className).toContain("text-good");
});

test("a dialog opens with its title and closes with Escape", async () => {
  const user = userEvent.setup();
  render(
    <Dialog>
      <DialogTrigger asChild>
        <Button>Nouveau client</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Nouveau client</DialogTitle>
        <DialogDescription>Renseignez le nom du client.</DialogDescription>
      </DialogContent>
    </Dialog>,
  );
  expect(screen.queryByRole("dialog")).toBeNull();

  await user.click(screen.getByRole("button", { name: "Nouveau client" }));
  expect(screen.getByRole("dialog", { name: "Nouveau client" })).toBeDefined();

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("the theme choice is applied to the page, remembered, and can go back to the device theme", async () => {
  const user = userEvent.setup();
  render(<ThemeToggle />);
  expect(screen.getByRole("button", { name: "Thème de l'appareil" }).getAttribute("aria-pressed")).toBe("true");

  await user.click(screen.getByRole("button", { name: "Thème sombre" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(screen.getByRole("button", { name: "Thème sombre" }).getAttribute("aria-pressed")).toBe("true");

  // A new visit starts from the remembered choice.
  delete document.documentElement.dataset.theme;
  initTheme();
  expect(document.documentElement.dataset.theme).toBe("dark");

  await user.click(screen.getByRole("button", { name: "Thème de l'appareil" }));
  expect(document.documentElement.dataset.theme).toBeUndefined();
  expect(localStorage.getItem("frutti-theme")).toBeNull();
});

test("the uploaded logo replaces the default mark and the tab icon, and the default icon comes back", () => {
  document.head.innerHTML = '<link rel="icon" type="image/svg+xml" href="/favicon.svg" />';
  function Branded({ logoUrl }: { logoUrl: string | null }) {
    useFavicon(logoUrl);
    return <Brand logoUrl={logoUrl} />;
  }

  const { container, rerender } = render(<Branded logoUrl="/api/organizations/1/logo?v=ab12" />);

  expect(container.querySelector("img")?.getAttribute("src")).toBe("/api/organizations/1/logo?v=ab12");
  const icon = document.head.querySelector('link[rel="icon"]');
  expect(icon?.getAttribute("href")).toBe("/api/organizations/1/logo?v=ab12");
  // The logo's own type is left to the browser: a forced one could hide a PNG logo.
  expect(icon?.getAttribute("type")).toBe("image/svg+xml");

  rerender(<Branded logoUrl={null} />);

  expect(container.querySelector("img")).toBeNull();
  expect(icon?.getAttribute("href")).toBe("/favicon.svg");
  expect(icon?.getAttribute("type")).toBe("image/svg+xml");
});

test("the bell counts the unread notifications and opens the one clicked", async () => {
  const user = userEvent.setup();
  const onOpen = vi.fn();
  const onReadAll = vi.fn();
  render(
    <NotificationBell
      unread={1}
      items={[
        { id: 2, text: "Sami a envoyé sa clôture", time: "17/10/2026 18:05", read: false },
        { id: 1, text: "Sami a commencé sa journée", time: "17/10/2026 07:30", read: true },
      ]}
      onOpen={onOpen}
      onReadAll={onReadAll}
      soundOn
      onToggleSound={() => undefined}
    />,
  );

  await user.click(screen.getByRole("button", { name: "Notifications : 1 non lue" }));
  expect(screen.getByRole("button", { name: "Son : activé" }).getAttribute("aria-pressed")).toBe("true");
  await user.click(screen.getByRole("button", { name: "Tout marquer lu" }));
  expect(onReadAll).toHaveBeenCalledOnce();
  await user.click(screen.getByText("Sami a envoyé sa clôture"));
  expect(onOpen).toHaveBeenCalledWith(2);
});
