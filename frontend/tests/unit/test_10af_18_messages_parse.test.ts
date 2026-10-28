import { createTranslator } from "next-intl";
import { describe, expect, it } from "vitest";

import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

type Tree = { [key: string]: string | Tree };

function keys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([k, v]) => (typeof v === "string" ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`)));
}

// Every message must be valid ICU: literal braces (e.g. a JSON example) need quoting, otherwise
// next-intl shows a fallback instead of the text. Missing arguments are expected here (no values
// are passed); only malformed messages fail.
describe("test_10af_18_messages_parse", () => {
  for (const [locale, messages] of [["en", en], ["tr", tr]] as const) {
    it(`parses every ${locale} message`, () => {
      const invalid: string[] = [];
      const t = createTranslator({
        locale,
        messages,
        onError: (error) => {
          if (error.code === "INVALID_MESSAGE") invalid.push(error.message);
        },
      });
      for (const key of keys(messages as Tree)) (t as (k: string) => string)(key);
      expect(invalid).toEqual([]);
    });
  }
});
