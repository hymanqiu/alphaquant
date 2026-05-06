<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## lightweight-charts (v5+)

The library touches `window` at import time, so importing it inside a regular React Server Component or even a `"use client"` component that's part of the server build will crash the Next.js 16 build with `ReferenceError: window is not defined`.

**Always split the chart into two files:**

```tsx
// foo-card.tsx — server-importable wrapper
"use client";
import dynamic from "next/dynamic";
const FooImpl = dynamic(() => import("./foo-impl"), { ssr: false });
export default function FooCard(props) { return <FooImpl {...props} />; }
```

```tsx
// foo-impl.tsx — client-only, free to import lightweight-charts
"use client";
import { createChart, CandlestickSeries, ... } from "lightweight-charts";
// ...useRef + useEffect, cleanup with chart.remove() on unmount.
```

**v5 API note**: series creation moved from `chart.addCandlestickSeries(...)` (v4) to
`chart.addSeries(CandlestickSeries, ...)` (v5). The `CandlestickSeries`/`LineSeries`/
`HistogramSeries` constants are named exports.

Reference implementation: `src/components/pulse/price-chart-card.tsx` (wrapper) +
`price-chart-impl.tsx` (chart logic).
