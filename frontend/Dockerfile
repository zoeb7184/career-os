# ─────────────────────────────────────────────────────────────────
#  Career OS — Frontend Production Dockerfile
#  Multi-stage: install deps → build → minimal standalone runtime.
#  Context is frontend/ itself (see frontend/.dockerignore) — this
#  service has no cross-directory dependency the way the backend does.
# ─────────────────────────────────────────────────────────────────

# ---- deps ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- build ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* variables are inlined into the client bundle at BUILD
# time by Next.js, not read at container runtime — so this has to be
# passed as a Docker build ARG (Railway calls these "build-time
# variables" — set it on the frontend service alongside the regular
# runtime env vars, or every client bundle bakes in the fallback below).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ---- runtime ----
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Railway injects PORT at runtime; 3000 is just the local-run default.
# HOSTNAME must be 0.0.0.0 (not the standalone server's localhost
# default) or the container listens on an address nothing outside it
# can reach.
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
EXPOSE $PORT

CMD ["node", "server.js"]
