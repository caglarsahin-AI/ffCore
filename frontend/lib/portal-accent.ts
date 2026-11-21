// The chat portal's accent colour (11-2, K-11-0005 S3). The server only checks that it is #rrggbb;
// this derives a tone per theme for the user's bubble and the send button: its text reads at
// >= 4.5:1 (WCAG AA body text) and it stands out from the page at >= 3:1 (WCAG non-text). A colour
// that already meets both is kept; otherwise it is mixed towards black (light theme, white text)
// or white (dark theme, dark text) in small steps until it does. Pure and deterministic, so the
// console previews exactly what the chat shows.

export type Theme = "light" | "dark";
export type AccentTone = { background: string; foreground: string; adjusted: boolean };

// The page backgrounds of styles/tokens.css (--background, light and dark) as numbers to compute
// with, not colours to paint: test_11_3_portal_accent checks them against the token file.
/* eslint-disable no-restricted-syntax -- contrast arithmetic needs the token values, see above */
export const PAGE_BACKGROUND: Record<Theme, string> = { light: "#eef2f7", dark: "#0b1220" };
const TEXT: Record<Theme, string> = { light: "#ffffff", dark: "#0b1220" };
/* eslint-enable no-restricted-syntax */
const TOWARDS: Record<Theme, Rgb> = { light: [0, 0, 0], dark: [255, 255, 255] };
const TEXT_MIN = 4.5;
const UI_MIN = 3;
const STEP = 0.02;

type Rgb = [number, number, number];
const HEX = /^#[0-9a-fA-F]{6}$/;

function parse(hex: string): Rgb {
  if (!HEX.test(hex)) throw new Error(`accent must be #rrggbb, got ${JSON.stringify(hex)}`);
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as Rgb;
}

function format(rgb: Rgb): string {
  return `#${rgb.map((c) => Math.round(c).toString(16).padStart(2, "0")).join("")}`;
}

function luminance(rgb: Rgb): number {
  const [r, g, b] = rgb.map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(parse(a)), luminance(parse(b))].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function tone(rgb: Rgb, theme: Theme): AccentTone {
  const target = TOWARDS[theme];
  for (let mix = 0; mix <= 1 + 1e-9; mix += STEP) {
    const candidate = format(rgb.map((c, i) => c + (target[i] - c) * Math.min(mix, 1)) as Rgb);
    if (contrast(TEXT[theme], candidate) >= TEXT_MIN && contrast(candidate, PAGE_BACKGROUND[theme]) >= UI_MIN) {
      return { background: candidate, foreground: TEXT[theme], adjusted: mix > 0 };
    }
  }
  // Unreachable: pure black / white meet both thresholds against these pages.
  throw new Error(`no readable ${theme} tone for ${format(rgb)}`);
}

export function accentTones(hex: string): Record<Theme, AccentTone> {
  const rgb = parse(hex);
  return { light: tone(rgb, "light"), dark: tone(rgb, "dark") };
}

export function isAccent(value: string): boolean {
  return HEX.test(value);
}

// CSS custom properties for a subtree (the chat screen, a preview); null: the brand primary.
export function accentStyle(hex: string | null | undefined): Record<string, string> {
  if (!hex) return {};
  const tones = accentTones(hex);
  return {
    "--chat-accent-light": tones.light.background,
    "--chat-accent-light-fg": tones.light.foreground,
    "--chat-accent-dark": tones.dark.background,
    "--chat-accent-dark-fg": tones.dark.foreground,
  };
}
