// API base URL.
//
// Production: empty string — frontend calls "/api/*" on its own origin and
// the production reverse proxy (Nginx, etc.) forwards to the backend with
// proper SSE streaming.
//
// Development: "http://127.0.0.1:8000" — connect EventSource directly to the
// backend. Next.js dev server's `rewrites` proxy buffers chunked SSE
// responses, so going through it would freeze the progress bar / thinking
// panel until the entire analysis completes. Backend CORS already allows
// localhost:3000.
//
// Override either default via NEXT_PUBLIC_API_URL.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "");
