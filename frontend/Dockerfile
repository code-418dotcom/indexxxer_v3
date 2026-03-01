# syntax=docker/dockerfile:1
FROM node:22-alpine AS base
WORKDIR /app

# ── dev target ─────────────────────────────────────────────────────────────────
# Install deps into the image; source code is mounted at runtime for hot reload.
FROM base AS dev
COPY package.json package-lock.json* ./
RUN npm install
# src/ is mounted via volume at runtime; this layer just needs deps + config files
COPY next.config.ts tsconfig.json tailwind.config.ts postcss.config.mjs ./
CMD ["npm", "run", "dev"]

# ── build target ───────────────────────────────────────────────────────────────
FROM base AS build
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
# Backend URL for the rewrite proxy (set at build time for static analysis)
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL}
RUN npm run build

# ── production target ──────────────────────────────────────────────────────────
FROM base AS prod
ENV NODE_ENV=production
COPY --from=build /app/public ./public
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
CMD ["node", "server.js"]
