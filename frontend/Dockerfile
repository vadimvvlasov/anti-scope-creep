# syntax=docker/dockerfile:1
# Static frontend for running the full system locally with compose.
# Production serves the same build from Cloudflare Pages (docs/architecture.md).

FROM node:22-bookworm-slim AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .
# Vite inlines VITE_* variables at build time, so the API URL is a build argument.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL \
    VITE_USE_MOCK=false
RUN npm run build


# Listens on 8080 as a non-root user.
FROM nginxinc/nginx-unprivileged:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/.output/public /usr/share/nginx/html
