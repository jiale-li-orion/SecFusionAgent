FROM node:22-alpine AS build
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
ARG PRODUCT_BASE=/
ENV PRODUCT_BASE=${PRODUCT_BASE}
RUN npm run build

FROM nginx:1.27-alpine
RUN mkdir -p /etc/nginx/auth /etc/nginx/snippets
COPY deploy/product-web/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/product-web/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /web/dist/ /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -q -O- http://127.0.0.1/healthz >/dev/null || exit 1
