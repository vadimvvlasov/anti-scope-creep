/** Shown when the build has no version: the dev server, local compose, tests. */
export const LOCAL_VERSION = "local";

/** The build version: deploy.yml sets VITE_APP_VERSION to the backend image tag (sha-<7 hex>). */
export const appVersion = (raw: string | undefined): string => raw?.trim() || LOCAL_VERSION;

export const APP_VERSION = appVersion(
  typeof import.meta !== "undefined" ? import.meta.env?.["VITE_APP_VERSION"] : undefined,
);
