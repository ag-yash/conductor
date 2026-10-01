# Build the browser bundle once, then serve only static files from Nginx.
FROM node:22-alpine AS build

WORKDIR /app

COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci

COPY dashboard ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY docker/dashboard.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
