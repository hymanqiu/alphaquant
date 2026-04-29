import type { NextConfig } from "next";

// Proxy /api/* to the FastAPI backend so frontend + backend share an origin.
// This avoids cross-origin cookie loss for EventSource (the SSE client
// doesn't send cookies cross-origin reliably across browsers/SameSite policies).
//
// In dev: http://localhost:3000/api/* → http://127.0.0.1:8001/api/*
// In prod: configure NEXT_PUBLIC_BACKEND_URL or change the rewrite target
//          to your backend's internal address.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
