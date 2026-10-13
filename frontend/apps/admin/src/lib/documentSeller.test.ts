import { describe, expect, it } from "vitest";

import { uniqueIdentifier } from "./documentSeller";

describe("uniqueIdentifier", () => {
  it("keeps the number and key letter of a Tunisian tax id, like the PDFs", () => {
    expect(uniqueIdentifier("1902781/R/N/M/000")).toBe("1902781R");
    expect(uniqueIdentifier(" 1902781 / r / N/M/000")).toBe("1902781R");
    expect(uniqueIdentifier("")).toBe("");
    expect(uniqueIdentifier("ABC/1")).toBe("");
  });
});
