# syntax=docker/dockerfile:1
#
# Imagen de producción de @ambienta/api (NestJS).
# Multi-stage: se compila con devDependencies y se ejecuta solo con las de
# producción, sobre un usuario no-root.
#
# Contexto de build esperado: la RAÍZ del monorepo (no apps/api), porque
# npm workspaces necesita el package-lock.json y los manifests de todos los
# workspaces para resolver dependencias de forma reproducible.
#   docker build -f apps/api/Dockerfile .

# ---------- Stage 1: dependencias ----------
FROM node:24-alpine AS deps
WORKDIR /repo

# Solo los manifests primero: si el código cambia pero las dependencias no,
# Docker reutiliza esta capa y se salta el npm ci completo.
COPY package.json package-lock.json ./
COPY apps/api/package.json apps/api/
COPY packages/shared/package.json packages/shared/

# `npm ci` respeta el lockfile exacto (build reproducible), a diferencia de install.
RUN npm ci --workspace @ambienta/api --include-workspace-root

# ---------- Stage 2: build ----------
FROM node:24-alpine AS builder
WORKDIR /repo

COPY --from=deps /repo/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY packages/shared ./packages/shared
COPY apps/api ./apps/api

RUN npm run build --workspace @ambienta/api

# Elimina las devDependencies dejando solo lo necesario en runtime.
RUN npm prune --omit=dev --workspace @ambienta/api --include-workspace-root

# ---------- Stage 3: runtime ----------
FROM node:24-alpine AS runner
WORKDIR /repo

ENV NODE_ENV=production

# `dumb-init` reenvía SIGTERM correctamente al proceso Node, de modo que
# enableShutdownHooks() alcance a cerrar las conexiones a Postgres/Redis.
RUN apk add --no-cache dumb-init

# Usuario sin privilegios: si la API se ve comprometida, no corre como root.
RUN addgroup -g 1001 nodejs && adduser -S -u 1001 -G nodejs ambienta

COPY --from=builder --chown=ambienta:nodejs /repo/node_modules ./node_modules
COPY --from=builder --chown=ambienta:nodejs /repo/packages/shared ./packages/shared
COPY --from=builder --chown=ambienta:nodejs /repo/apps/api/dist ./apps/api/dist
COPY --from=builder --chown=ambienta:nodejs /repo/apps/api/package.json ./apps/api/

USER ambienta

EXPOSE 3001

# Healthcheck contra el liveness probe (no el readiness: si Postgres se cae,
# reiniciar el contenedor de la API no arregla nada).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:3001/health',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"

ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "apps/api/dist/main.js"]
