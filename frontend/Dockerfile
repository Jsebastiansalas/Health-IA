# Etapa 1: compila la SPA. Etapa 2: Caddy sirve los estáticos, termina TLS y hace de proxy a la API.
FROM node:24-alpine AS compilacion
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=compilacion /app/dist /srv
