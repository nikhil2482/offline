FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30-alpine
# Pick up OS security fixes released after the base image was built.
USER root
RUN apk upgrade --no-cache
USER 101
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
