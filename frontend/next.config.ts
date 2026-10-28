import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

import { backendUrl } from "./lib/backend";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  // C6: the browser calls the API on the console origin; Next.js forwards it to the backend, so
  // the session cookie stays first-party and SameSite=Strict holds. Fixed at build time.
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backendUrl()}/api/v1/:path*` }];
  },
};

export default withNextIntl(nextConfig);
