# syntax=docker/dockerfile:1
#
# Imagen de producción de @ambienta/web (Next.js 14, App Router).
# Usa el output `standalone` de Next para una imagen mínima.
#
# Contexto de build esperado: la RAÍZ del monorepo (no apps/web).
#   docker build -f apps/web/Dockerfile .

# ---------- Stage 1: dependencias ----------
FROM node:24-alpine AS deps
WORKDIR /repo

COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
COPY packages/shared/package.json packages/shared/

RUN npm ci --workspace @ambienta/web --include-workspace-root

# ---------- Stage 2: build ----------
FROM node:24-alpine AS builder
WORKDIR /repo

COPY --from=deps /repo/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY packages/shared ./packages/shared
COPY apps/web ./apps/web

# La URL de la API se hornea en el bundle del cliente en tiempo de BUILD
# (las variables NEXT_PUBLIC_* no se leen en runtime), así que cada entorno
# necesita su propia imagen o su propio valor de build-arg.
ARG NEXT_PUBLIC_API_URL=http://localhost:3001/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build --workspace @ambienta/web

# ---------- Stage 3: runtime ----------
FROM node:24-alpine AS runner
WORKDIR /repo

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN apk add --no-cache dumb-init
RUN addgroup -g 1001 nodejs && adduser -S -u 1001 -G nodejs ambienta

# El output standalone ya trae su propio node_modules mínimo; no se copia el
# node_modules del monorepo.
COPY --from=builder --chown=ambienta:nodejs /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=ambienta:nodejs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=ambienta:nodejs /repo/apps/web/public ./apps/web/public

USER ambienta

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:3000/login',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"

ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "apps/web/server.js"]
