#!/bin/sh
# Escribe el token de las métricas y la configuración final, y arranca Prometheus.
set -eu
: "${METRICS_TOKEN:?defina METRICS_TOKEN: sin él la API y el agente no publican métricas}"
: "${URL_SITIO:?defina URL_SITIO (la dirección pública, con https)}"

(umask 077 && printf '%s' "$METRICS_TOKEN" > /tmp/metrics_token)
sed -e "s|__URL_SITIO__|${URL_SITIO}|g" -e "s|__INTERVALO__|${INTERVALO:-30s}|g" \
    /etc/medtender/prometheus.yml.plantilla > /tmp/prometheus.yml

exec /bin/prometheus --config.file=/tmp/prometheus.yml \
    --storage.tsdb.path=/prometheus --storage.tsdb.retention.time=30d
