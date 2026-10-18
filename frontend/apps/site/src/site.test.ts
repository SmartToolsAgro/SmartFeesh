import { expect, test } from "vitest";

import { addToCart, estimate, lineTotal, parseKilos, removeFromCart, setQuantity } from "./cart";
import { pictureOf } from "./media";
import { normalizePhone, shownPhone, telHref, whatsappHref } from "./phone";

test("phone numbers are written like the server writes them", () => {
  expect(normalizePhone("98123456")).toBe("+216 98 123 456");
  expect(normalizePhone("98 123 456")).toBe("+216 98 123 456");
  expect(normalizePhone("+216 98.123.456")).toBe("+216 98 123 456");
  expect(normalizePhone("0021674123456")).toBe("+216 74 123 456");
  expect(normalizePhone("+33 6 12 34 56 78")).toBe("+33612345678");
});

test("a wrong phone number is refused", () => {
  for (const typed of ["", "1234", "12345678", "98 123 45", "+216 98 123 4567", "téléphone", "+1234"]) {
    expect(normalizePhone(typed)).toBeNull();
  }
});

test("kilos are positive decimals with at most 3 decimals, up to 10 000", () => {
  expect(parseKilos("12,5")).toBe("12.5");
  expect(parseKilos(" 3 ")).toBe("3");
  expect(parseKilos("0")).toBeNull();
  expect(parseKilos("-2")).toBeNull();
  expect(parseKilos("1.2345")).toBeNull();
  expect(parseKilos("10000.001")).toBeNull();
  expect(parseKilos("abc")).toBeNull();
});

test("the basket adds to a product already in it, changes and removes lines", () => {
  let lines = addToCart([], 1, "2.5");
  lines = addToCart(lines, 2, "1");
  lines = addToCart(lines, 1, "0.75");
  expect(lines).toEqual([
    { product: 1, quantity: "3.250" },
    { product: 2, quantity: "1" },
  ]);
  expect(addToCart([{ product: 1, quantity: "9999" }], 1, "5")).toEqual([{ product: 1, quantity: "10000.000" }]);
  expect(setQuantity(lines, 2, "4")).toEqual([
    { product: 1, quantity: "3.250" },
    { product: 2, quantity: "4" },
  ]);
  expect(removeFromCart(lines, 1)).toEqual([{ product: 2, quantity: "1" }]);
});

test("the indicative total counts only the products with a web price, to the millime", () => {
  expect(lineTotal("12.5", "29.5")).toBe("368.750");
  expect(lineTotal("0.333", "1.001")).toBe("0.333");
  const prices = new Map<number, string | null>([
    [1, "29.500"],
    [2, null],
  ]);
  expect(
    estimate(
      [
        { product: 1, quantity: "2" },
        { product: 2, quantity: "3" },
      ],
      prices,
    ),
  ).toBe("59.000");
  expect(estimate([{ product: 2, quantity: "3" }], prices)).toBeNull();
});

test("each product gets a picture from its name, then from its drawing kind", () => {
  expect(pictureOf({ name: "Rouget de roche", illustration: "fish", photo_url: null })).toBe("/media/p-rouget.webp");
  expect(pictureOf({ name: "Crevette royale", illustration: "fish", photo_url: null })).toBe("/media/p-crevette.webp");
  expect(pictureOf({ name: "Seiche", illustration: "squid", photo_url: null })).toBe("/media/p-poulpe.webp");
  expect(pictureOf({ name: "Mélange friture", illustration: "mix", photo_url: null })).toBe(
    "/media/catch-flatlay.webp",
  );
  expect(pictureOf({ name: "Dorade", illustration: "fish", photo_url: "/api/v1/site/products/3/photo?v=a" })).toBe(
    "/api/v1/site/products/3/photo?v=a",
  );
});

test("the company's number is shown without +216, and called or messaged with it", () => {
  expect(shownPhone("+216 74 123 456")).toBe("74 123 456");
  expect(shownPhone("+33612345678")).toBe("+33612345678");
  expect(telHref("+216 74 123 456")).toBe("tel:+21674123456");
  expect(whatsappHref("+216 98 123 456")).toBe("https://wa.me/21698123456");
});
