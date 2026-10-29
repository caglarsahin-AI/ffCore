import type { MetadataRoute } from "next";

import en from "@/messages/en.json";

// Served at /manifest.webmanifest and linked by the Next.js file convention. Name and description
// come from the source locale's messages (one key, ARCH-13); a manifest has no locale of its own.
// A manifest cannot read CSS variables, so the brand navy (assets/icons/README.md) is the one
// literal colour in the source tree; the no-hard-coded-colour rule is waived for this line only.
// eslint-disable-next-line no-restricted-syntax -- manifest colour, not a component style
const BRAND_NAVY = "#0A192F";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: en.Home.title,
    short_name: en.Home.title,
    description: en.Home.subtitle,
    start_url: "/",
    display: "standalone",
    background_color: BRAND_NAVY,
    theme_color: BRAND_NAVY,
    icons: [
      { src: "/brand/ffcore-icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/ffcore-icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
