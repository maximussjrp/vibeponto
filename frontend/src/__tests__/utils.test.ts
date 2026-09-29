import { describe, expect, it } from "vitest";

import { formatCoordinates, toFiniteNumber } from "@/lib/utils";

describe("numeric API normalization", () => {
  it("converts decimal strings returned by the API", () => {
    expect(toFiniteNumber("-20.76120000")).toBe(-20.7612);
    expect(toFiniteNumber("-49.33410000")).toBe(-49.3341);
  });

  it("formats string coordinates without throwing", () => {
    expect(formatCoordinates("-20.76120000", "-49.33410000")).toBe(
      "-20.7612, -49.3341"
    );
  });

  it("rejects missing and invalid numeric values", () => {
    expect(toFiniteNumber("")).toBeUndefined();
    expect(toFiniteNumber(null)).toBeUndefined();
    expect(toFiniteNumber("invalid")).toBeUndefined();
    expect(formatCoordinates("-20.7612", null)).toBeNull();
  });
});
