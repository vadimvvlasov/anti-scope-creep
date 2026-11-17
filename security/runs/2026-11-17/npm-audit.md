# Frontend `npm audit`, 2026-11-17 (issue #109)

Before: 17 vulnerabilities (5 critical, 3 high, 9 moderate) in the `main` lockfile
([`npm-audit-before.json`](npm-audit-before.json), `npm audit --package-lock-only`).
After: **0**, with and without dev dependencies ([`npm-audit-after.json`](npm-audit-after.json),
[`npm-audit-after-prod.json`](npm-audit-after-prod.json)). No `npm audit fix --force`.

## Version changes (`frontend/package.json`)

| Package | Before | After | Why |
|---|---|---|---|
| `@tanstack/react-start` | 1.168.32 | 1.169.5 | 5 critical: server-function XSS in `react-start`, `start-server-core`, `start-plugin-core`, `react-start-server`, `react-start-rsc` |
| `@tanstack/react-router` | 1.170.18 | 1.170.46 | the version `react-start` 1.169.5 pins, so only one router is installed |
| `@tanstack/router-plugin` | 1.168.23 | 1.169.0 | the version `start-plugin-core` 1.171.56 pins; brings `zod` 4.6.7 to the TanStack tooling |
| `vite` | 8.1.5 | 8.3.8 | high: dev-server cross-origin script execution, `server.fs.allow` bypass; `launch-editor` (dev server) |
| `zod` | ^3.25.76 | ^4.6.7 | high: memory exhaustion on hostile input; nothing in `src/` imports `zod` (a leftover of the Lovable export), so the major version change cannot break the app |
| `typescript-eslint` | ^8.56.1 (8.71.0 installed) | ^8.73.0 | moderate, dev only: vulnerable `minimatch` through `@typescript-eslint/*` |

`npm audit fix` (without `--force`) then updated transitive `seroval` (1.8.1), `fast-uri` (3.1.9) and
`minimatch` (11.0.9).

## Decision per finding

| Finding | Reachable in production before? | Decision |
|---|---|---|
| TanStack Start server-function XSS (5 critical) | No: Workers serve only the static `.output/public`; the app has no `createServerFn` | fixed by the version change |
| `vite`, `launch-editor` (high) | No: dev server only | fixed |
| `zod` (high) | No: not imported by the app; in the TanStack build tooling only | fixed |
| `seroval` (moderate, 2) | No: server-side serialization of TanStack Start, not run on Workers | fixed |
| `fast-uri` (moderate) | No: build tooling | fixed |
| `typescript-eslint`, `minimatch` (moderate, dev) | No: lint only | fixed |

No finding is left, so nothing is accepted or deferred.

## Code change forced by the update

`@tanstack/react-router` 1.170.46 types the error of an error boundary as `unknown`. The root
`ErrorComponent` (`src/routes/__root.tsx`) now takes the router's own `ErrorComponentProps`; it only logs
and reports the error, both of which accept `unknown`.

## Checks

- `npm test`: 85 passed. `npm run build`: passes. `npm run lint`: 0 errors (the 9 warnings are the same as before).
- `tsc --noEmit`: the one remaining error is in `src/services/__tests__/mockClient.test.ts` and is on `main`
  too; not touched here.
- `make e2e`: run in CI (port 3000 was taken on the machine that made this change).
