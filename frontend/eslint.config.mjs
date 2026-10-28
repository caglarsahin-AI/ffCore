import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

// Hard-coded colours (brief 10 "Ortak"): only token classes (bg-background, text-foreground...).
// Palette utilities, hex, rgb()/hsl(). A hex inside an attribute selector such as
// [stroke='#ccc'] (shadcn chart.tsx neutralising Recharts defaults) is not a colour we set.
const PALETTE =
  "(bg|text|border|ring|fill|stroke|from|via|to|outline|divide|decoration|shadow|accent|caret)-" +
  "(white|black|(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|" +
  "cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\\d{2,3})\\b";
const COLOUR = `/(\\b${PALETTE})|((?<!=')#[0-9a-fA-F]{3,8}\\b)|(\\b(rgb|rgba|hsl|hsla)\\()/`;
const COLOUR_MESSAGE = "Hard-coded colour: use a theme token class from styles/tokens.css.";
const COLOUR_RULES = [
  { selector: `Literal[value=${COLOUR}]`, message: COLOUR_MESSAGE },
  { selector: `TemplateElement[value.raw=${COLOUR}]`, message: COLOUR_MESSAGE },
];
// jsx-no-literals ignores props, so text in accessibility attributes slipped through (FOLLOWUP-44).
const ATTRIBUTE_TEXT = {
  selector: "JSXAttribute[name.name=/^(aria-label|title|placeholder|alt)$/] > Literal[value=/[A-Za-z]/]",
  message: "User-visible attribute text comes from messages/*.json (t(...)).",
};

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": ["error", ...COLOUR_RULES],
    },
  },
  {
    // User-visible text comes from messages/*.json (en source, tr translation).
    files: ["app/**/*.tsx", "components/**/*.tsx"],
    rules: {
      "react/jsx-no-literals": ["error", { noStrings: false, ignoreProps: true }],
      // Flat config replaces a rule's options per block: repeat the colour rules here.
      "no-restricted-syntax": ["error", ...COLOUR_RULES, ATTRIBUTE_TEXT],
    },
  },
  {
    files: ["tests/**"],
    rules: { "react/jsx-no-literals": "off", "no-restricted-syntax": "off" },
  },
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      "build/**",
      "next-env.d.ts",
      "playwright-report/**",
      "test-results/**",
    ],
  },
];

export default eslintConfig;
