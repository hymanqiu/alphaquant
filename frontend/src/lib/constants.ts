// API base URL.
//
// Default is empty string — frontend calls go to "/api/*" on its own origin,
// and Next.js rewrites (see next.config.ts) proxy them to the backend.
// This eliminates cross-origin cookie loss for EventSource.
//
// Set NEXT_PUBLIC_API_URL only if you specifically need to bypass the proxy
// (e.g. running frontend and backend on different domains in production
// with proper CORS + SameSite=None cookies).
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
