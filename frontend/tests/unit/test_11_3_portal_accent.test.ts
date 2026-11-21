import { describe, expect, it } from "vitest";

import { PAGE_BACKGROUND, accentTones, contrast } from "@/lib/portal-accent";

// 11-2 (K-11-0005 S3): one accent hex gives a light and a dark tone for the user bubble and the
// send button; the text on it reads at >= 4.5:1 and the tone stands out from the page at >= 3:1,
// whatever colour was picked. The derivation is pure and deterministic.

const SAMPLES = ["#0F766E", "#ffffff", "#000000", "#ffff00", "#ff0000", "#1E3A5F", "#60A5FA", "#808080"];

describe("test_11_3_portal_accent", () => {
  it("measures contrast as WCAG does", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contrast("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
    expect(contrast("#767676", "#ffffff")).toBeCloseTo(4.54, 1);
  });

  for (const hex of SAMPLES) {
    it(`derives readable tones for ${hex} in both themes`, () => {
      const tones = accentTones(hex);
      for (const theme of ["light", "dark"] as const) {
        const tone = tones[theme];
        expect(tone.background).toMatch(/^#[0-9a-f]{6}$/);
        expect(contrast(tone.foreground, tone.background)).toBeGreaterThanOrEqual(4.5);
        expect(contrast(tone.background, PAGE_BACKGROUND[theme])).toBeGreaterThanOrEqual(3);
      }
    });
  }

  it("keeps a colour that already works and says whether it changed", () => {
    const tones = accentTones("#0F766E");
    expect(tones.light.background).toBe("#0f766e");
    expect(tones.light.adjusted).toBe(false);
    expect(accentTones("#ffff00").light.adjusted).toBe(true);
  });

  it("is deterministic and case-insensitive", () => {
    expect(accentTones("#0F766E")).toEqual(accentTones("#0f766e"));
  });

  it("refuses a value that is not a #rrggbb colour (no silent default)", () => {
    expect(() => accentTones("teal")).toThrow();
  });
});
