# syntax=docker/dockerfile:1
# Frontend image. Targets:
#   dev  -> Vite dev server on :5173 (compose bind-mounts the source over /app,
#           plus an anonymous volume on /app/node_modules so the image's deps stay visible)
#   prod -> nginx serving the static build on :8080 and proxying /api/ to api:8000
ARG NODE_IMAGE=node:24-alpine
ARG NGINX_IMAGE=nginx:1.30-alpine

# ---------- stage 1: node (dependencies + source; also the dev target) ----------
FROM ${NODE_IMAGE} AS dev
WORKDIR /app
ENV CI=true
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# Production bundle (type-check + vite build). Only built when --target prod is requested.
FROM dev AS build
RUN npm run build

# ---------- stage 2: nginx (prod target) ----------
FROM ${NGINX_IMAGE} AS prod
# The image entrypoint renders /etc/nginx/templates/*.template into /etc/nginx/conf.d/ with envsubst;
# NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 makes it export NGINX_LOCAL_RESOLVERS from /etc/resolv.conf.
ENV NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

# compose (dev) needs:  volumes: ["./frontend:/app", "/app/node_modules"]
