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

# Clave publica de Clerk (ADR-006). Las NEXT_PUBLIC_* se resuelven en tiempo de
# build, no de arranque: si no entra aca no existe en el bundle del navegador y
# el login no funciona por mucho que este en el .env del servidor.
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

# Nombre del JWT Template que trae el claim `tenant_id`. El codigo asume
# `default`; esto existe para cuando lo renombren en Clerk. Un `build-arg` que
# el Dockerfile no declara se ignora con una advertencia facil de pasar por
# alto, asi que las que el compose pasa tienen que estar declaradas aca.
ARG NEXT_PUBLIC_CLERK_JWT_TEMPLATE=default
ENV NEXT_PUBLIC_CLERK_JWT_TEMPLATE=$NEXT_PUBLIC_CLERK_JWT_TEMPLATE

# Empresa del link publico del Cliente Invitado (RF-02). Sin ella la pantalla
# /acceso-invitado exige `?empresa=<uuid>` en la URL en vez de elegir una
# empresa al azar.
ARG NEXT_PUBLIC_EMPRESA_INVITADO=
ENV NEXT_PUBLIC_EMPRESA_INVITADO=$NEXT_PUBLIC_EMPRESA_INVITADO

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
# `apps/web/public` tiene que existir en el repo aunque este vacio: `COPY` no
# admite "si existe" y falla el build entero si falta. **Y faltaba**: la imagen
# de produccion de la web no se podia construir, asi que `up -d --build` se
# caia en el primer intento. En desarrollo no se nota porque `next dev` no
# necesita el directorio. Por eso esta el `.gitkeep`.
COPY --from=builder --chown=ambienta:nodejs /repo/apps/web/public ./apps/web/public

USER ambienta

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:3000/login',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"

ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "apps/web/server.js"]
