# Etapa 1: compila la SPA. Etapa 2: Caddy sirve los estáticos, termina TLS y hace de proxy a la API.
FROM node:24-alpine AS compilacion
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Vite las incrusta al compilar: sin pasarlas aquí, la web sale sin ellas.
ARG VITE_URL_PUBLICA=""
ARG VITE_RESPONSABLE=""
ARG VITE_CONTACTO_PRIVACIDAD=""
ARG VITE_ERRORES_DSN=""
ENV VITE_URL_PUBLICA=$VITE_URL_PUBLICA VITE_RESPONSABLE=$VITE_RESPONSABLE VITE_CONTACTO_PRIVACIDAD=$VITE_CONTACTO_PRIVACIDAD VITE_ERRORES_DSN=$VITE_ERRORES_DSN
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=compilacion /app/dist /srv
