###############################################################################
# frontend/Dockerfile — Multi-stage build for the React/Vite frontend
#
# Stage 1 (builder): Node 20 Alpine — installs deps, runs type-check, builds
#                    the static bundle.
# Stage 2 (production): nginx:alpine — serves the compiled bundle behind a
#                       lightweight, hardened nginx config.
#
# Build args:
#   NODE_ENV              default production
#   VITE_API_BASE_URL     injected at build time (baked into bundle)
#   VITE_WS_BASE_URL      injected at build time
###############################################################################

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: builder
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

ARG NODE_ENV=production
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_WS_BASE_URL=/ws

ENV NODE_ENV=${NODE_ENV} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_BASE_URL=${VITE_WS_BASE_URL} \
    # Disable Next.js telemetry / Vite analytics
    NEXT_TELEMETRY_DISABLED=1 \
    # Increase Node heap for large builds
    NODE_OPTIONS="--max-old-space-size=4096"

WORKDIR /app

# Install dependencies first (better caching).
# Copying only the lock files before source means this layer is invalidated
# only when package.json or package-lock.json change, not on every code edit.
COPY package.json package-lock.json ./

# `npm ci` is stricter than `npm install` — uses the lock file exactly.
RUN npm ci --prefer-offline --no-audit --no-fund

# Copy the rest of the source
COPY . .

# Type-check before building — fail fast on TypeScript errors.
RUN npm run type-check

# Build the production bundle
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: production (nginx)
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production

# Remove the default nginx config and replace with our app-specific one.
RUN rm /etc/nginx/conf.d/default.conf

# Copy compiled static assets from the builder stage.
# Vite outputs to /app/dist by default.
COPY --from=builder /app/dist /usr/share/nginx/html

# Per-container nginx config — handles SPA routing (all paths -> index.html).
# The top-level nginx.conf is mounted at runtime via Docker volume for the
# full reverse-proxy; this inner config handles the static-file serving.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Ensure the nginx worker can write to its cache/tmp directories.
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && chown -R nginx:nginx /etc/nginx/conf.d \
    # Allow nginx to run as non-root (writes PID to /tmp instead of /run)
    && touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
