// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
    // SPA mode: the app shell is prerendered to /_shell.html and serves every app route (deep links
    // via nginx.conf locally and public/_redirects on Cloudflare). The guest landing page `/` is
    // prerendered with its content to /index.html, so link previews and crawlers get the text
    // (docs/spec.md "Landing page").
    // maskPath must be a route other than "/", or the shell replaces the landing page in the list
    // of pages; the shell renders only the root layout whatever the path.
    spa: { enabled: true, maskPath: "/login", prerender: { outputPath: "/_shell" } },
    pages: [{ path: "/", prerender: { enabled: true } }],
    // Only these pages: following the landing page's links would prerender app routes too.
    prerender: { crawlLinks: false },
  },
});
