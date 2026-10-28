import { getRequestConfig } from "next-intl/server";

// Tek dil: tr. Anahtarlar İngilizce, metinler messages/tr.json'da.
export default getRequestConfig(async () => ({
  locale: "tr",
  messages: (await import("../messages/tr.json")).default,
}));
