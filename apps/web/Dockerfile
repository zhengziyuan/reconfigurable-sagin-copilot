FROM node:22-alpine AS build

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json

RUN corepack enable && pnpm install --filter rsagin-web --frozen-lockfile

COPY apps/web ./apps/web

ARG VITE_GIS_STREET_TILES
ARG VITE_GIS_SATELLITE_TILES
ARG VITE_GIS_STREET_ATTRIBUTION
ARG VITE_GIS_SATELLITE_ATTRIBUTION
ENV VITE_GIS_STREET_TILES=$VITE_GIS_STREET_TILES \
    VITE_GIS_SATELLITE_TILES=$VITE_GIS_SATELLITE_TILES \
    VITE_GIS_STREET_ATTRIBUTION=$VITE_GIS_STREET_ATTRIBUTION \
    VITE_GIS_SATELLITE_ATTRIBUTION=$VITE_GIS_SATELLITE_ATTRIBUTION

RUN pnpm --dir apps/web build

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80
