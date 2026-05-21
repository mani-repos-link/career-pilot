FROM node:22-alpine AS build

WORKDIR /repo

RUN corepack enable && corepack prepare pnpm@11.1.2 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/
COPY packages/utils/package.json ./packages/utils/
RUN pnpm install --frozen-lockfile

COPY packages ./packages
COPY apps/web ./apps/web
COPY tsconfig.json vite.config.ts ./

ARG VITE_API_BASE_URL=http://localhost:8080
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm --filter web build


FROM nginx:1.27-alpine AS runtime

COPY apps/web/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
