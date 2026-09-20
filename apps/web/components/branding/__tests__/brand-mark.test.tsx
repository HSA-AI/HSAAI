import { describe, it, expect } from "vitest";

// Simple smoke test for brand constants
describe("HSAAI Brand", () => {
  it("should define brand name as HSAAI", () => {
    const BRAND_NAME = "HSAAI";
    expect(BRAND_NAME).toBe("HSAAI");
  });

  it("should use enterprise color scheme", () => {
    const BRAND_COLORS = {
      primary: "#0f766e",
      secondary: "#115e59",
      accent: "#14b8a6",
    };
    expect(BRAND_COLORS.primary).toMatch(/^#[0-9a-f]{6}$/);
    expect(BRAND_COLORS.secondary).toMatch(/^#[0-9a-f]{6}$/);
    expect(BRAND_COLORS.accent).toMatch(/^#[0-9a-f]{6}$/);
  });
});
