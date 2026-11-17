import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

import { LandingPage } from "@/components/landing/landing-page";
import { LANDING_TITLE } from "@/lib/landing-copy";
import { LOGIN_VALUE_LINE } from "@/lib/login-copy";
import { getToken } from "@/services/api";

// Built by `npm run build` as a static `index.html` (vite.config.ts), so link previews and crawlers
// get the text. The image is `public/og-image.png` (docs/spec.md "Landing page"); previews need an
// absolute URL, so deploy.yml sets VITE_SITE_URL to the frontend's address.
const SITE_URL = String(import.meta.env["VITE_SITE_URL"] ?? "").replace(/\/+$/, "");
const OG_IMAGE = `${SITE_URL}/og-image.png`;

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: LANDING_TITLE },
      { name: "description", content: LOGIN_VALUE_LINE },
      { property: "og:title", content: LANDING_TITLE },
      { property: "og:description", content: LOGIN_VALUE_LINE },
      { property: "og:type", content: "website" },
      ...(SITE_URL ? [{ property: "og:url", content: `${SITE_URL}/` }] : []),
      { property: "og:image", content: OG_IMAGE },
      { property: "og:image:width", content: "1200" },
      { property: "og:image:height", content: "630" },
      { name: "twitter:image", content: OG_IMAGE },
    ],
  }),
  component: Index,
});

/** A guest sees the landing page; a stored session goes straight to Contract History. */
function Index() {
  const navigate = useNavigate();

  useEffect(() => {
    if (getToken()) void navigate({ to: "/history", replace: true });
  }, [navigate]);

  return <LandingPage />;
}
