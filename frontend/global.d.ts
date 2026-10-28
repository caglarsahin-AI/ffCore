import type messages from "./messages/en.json";

// Typed message keys: tsc fails on a key missing from the source locale.
declare module "next-intl" {
  interface AppConfig {
    Messages: typeof messages;
  }
}
