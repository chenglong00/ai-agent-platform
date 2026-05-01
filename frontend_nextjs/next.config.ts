import type { NextConfig } from "next";

/** Server-side rewrite target (browser never sees this). Use 127.0.0.1 to avoid IPv6 localhost quirks. */
const backendProxyTarget =
  process.env.BACKEND_PROXY_TARGET?.trim().replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  reactCompiler: true,
  // Disable Next's automatic gzip on responses — gzip block buffering breaks
  // streaming for our SSE chat endpoint and we don't need compression in dev.
  compress: false,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendProxyTarget}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
