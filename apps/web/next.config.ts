import type { NextConfig } from "next";

// The browser only ever talks to this Next.js server. /api/* is proxied
// server-side to the FastAPI backend, so no backend origin or localhost
// URL ever appears in browser code, and CORS is a non-issue in normal use.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
