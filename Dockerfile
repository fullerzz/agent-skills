FROM node:26-alpine AS build
# git: VitePress lastUpdated reads commit timestamps
RUN apk add --no-cache git && npm install -g pnpm@12.4.2
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm docs:build

FROM nginx:1.31-alpine
COPY docs/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/docs/.vitepress/dist /usr/share/nginx/html
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1
