#!/bin/bash
# Prueba de punta a punta del monitoreo con contenedores reales y datos inventados:
# reglas (promtool) → Prometheus lee las métricas con token y el estado de los respaldos →
# dispara la alerta → Alertmanager la envía por SMTP a un buzón falso → Grafana carga el panel.
# No toca los contenedores del proyecto ni envía correos reales. Desde la raíz:  bash infra/scripts/probar_monitoreo.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1

raiz="$(cd "$(dirname "$0")/../.." && pwd)"
command -v cygpath > /dev/null && raiz="$(cygpath -m "$raiz")"
id="mtmon-$$"
fallos=0
# Las mismas versiones que despliega el compose.
imagen() { grep -oE "image: $1:[^ ]+" "$raiz/infra/docker-compose.monitoreo.yml" | head -1 | cut -d' ' -f2; }
PROM="$(imagen prom/prometheus)"
ALERT="$(imagen prom/alertmanager)"
NODO="$(imagen prom/node-exporter)"
NEGRA="$(imagen prom/blackbox-exporter)"
GRAF="$(imagen grafana/grafana)"

limpiar() {
    docker rm -f $(docker ps -aq --filter "name=$id-") > /dev/null 2>&1 || true
    docker volume rm "$id-estado" > /dev/null 2>&1 || true
    docker network rm "$id" > /dev/null 2>&1 || true
}
trap limpiar EXIT

comprobar() { # comprobar "nombre" comando...
    local nombre="$1" salida
    shift
    if salida="$("$@" 2>&1)"; then
        echo "OK     $nombre"
    else
        echo "FALLA  $nombre"
        echo "$salida" | tail -12 | sed 's/^/         /'
        fallos=$((fallos + 1))
    fi
}
esperar() { # esperar segundos comando...
    local hasta=$((SECONDS + $1))
    shift
    until "$@"; do
        [ "$SECONDS" -lt "$hasta" ] || return 1
        sleep 3
    done
}

comprobar "las reglas pasan sus pruebas" \
    docker run --rm -v "$raiz/infra/monitoreo:/m:ro" -w /m --entrypoint promtool "$PROM" test rules alertas_test.yml
comprobar "la configuración de la sonda del sitio es válida" \
    docker run --rm -v "$raiz/infra/monitoreo:/m:ro" "$NEGRA" --config.file=/m/blackbox.yml --config.check

docker network create "$id" > /dev/null
docker volume create "$id-estado" > /dev/null
# Estado de respaldos inventado: la restauración de prueba falló.
docker run --rm -v "$id-estado:/estado" python:3.12-slim sh -c \
    'printf "medtender_respaldo_ultimo_ok_timestamp_segundos %s\nmedtender_respaldo_remoto_configurado 0\nmedtender_restauracion_fallo 1\n" "$(date +%s)" > /estado/respaldos.prom'

docker run -d --name "$id-buzon" --network "$id" --network-alias buzon -v "$raiz/infra/scripts:/s:ro" python:3.12-slim \
    python /s/monitoreo_falsos.py smtp > /dev/null
for servicio in api agente; do
    docker run -d --name "$id-$servicio" --network "$id" --network-alias "$servicio" -v "$raiz/infra/scripts:/s:ro" \
        python:3.12-slim sh -c "sed 's/8000/$([ $servicio = api ] && echo 8080 || echo 8000)/' /s/monitoreo_falsos.py > /tmp/f.py && python /tmp/f.py metricas" > /dev/null
done
docker run -d --name "$id-estado" --network "$id" --network-alias estado-respaldos -v "$id-estado:/estado:ro" "$NODO" \
    --collector.disable-defaults --collector.textfile --collector.textfile.directory=/estado > /dev/null

# Reglas sin esperas («for») para no tardar horas: su lógica ya la prueba promtool; aquí se prueba el camino.
copia="$(mktemp -d)"
command -v cygpath > /dev/null && copia="$(cygpath -m "$copia")"
cp "$raiz"/infra/monitoreo/* "$copia"/ 2> /dev/null || true
sed -i '/^ *for: /d' "$copia/alertas.yml"
# En Linux, mktemp -d deja la carpeta solo para su dueño y Prometheus y Alertmanager corren sin privilegios
# («nobody»): no podrían leer su configuración. (Docker para Windows no aplica estos permisos.)
chmod 755 "$copia"
chmod 644 "$copia"/*

docker run -d --name "$id-alertmanager" --network "$id" --network-alias alertmanager -v "$copia:/etc/medtender:ro" \
    -e ALERTAS_CORREO=alertas@prueba.local -e SMTP_HOST=buzon -e SMTP_PORT=25 -e CORREO_REMITENTE=medtender@prueba.local \
    -e SMTP_REQUIERE_TLS=false -e ESPERA_DE_AGRUPACION=2s \
    --entrypoint /bin/sh "$ALERT" /etc/medtender/arrancar-alertmanager.sh > /dev/null
docker run -d --name "$id-prometheus" --network "$id" --network-alias prometheus -v "$copia:/etc/medtender:ro" \
    -e METRICS_TOKEN=prueba -e URL_SITIO=http://api:8080/metrics -e INTERVALO=3s \
    --entrypoint /bin/sh "$PROM" /etc/medtender/arrancar-prometheus.sh > /dev/null

consulta() { docker exec "$id-prometheus" wget -qO- "http://127.0.0.1:9090/api/v1/query?query=$1" 2> /dev/null; }
leidos() { [ "$(consulta 'sum(up%7Bjob%3D~%22api%7Cagente%7Crespaldos%22%7D)' | grep -c '"3"')" = 1 ]; }
comprobar "Prometheus lee la API y el agente con el token, y el estado de los respaldos" esperar 90 leidos

llego() { docker logs "$id-buzon" 2>&1 | grep -q "FIN-CORREO"; }
comprobar "la alerta llega por correo" esperar 150 llego
# Sin esperas, antes puede llegar otro correo (p. ej. «servicio caído» mientras arrancan): se espera el que importa.
el_de_restauracion() { docker logs "$id-buzon" 2>&1 | awk '/^CORREO /{c=""; d=1} d{c=c $0 "\n"} /^FIN-CORREO$/{d=0; if (c ~ /asunto=MedTender \[firing\] RestauracionFallida/) printf "%s", c}'; }
llego_restauracion() { [ -n "$(el_de_restauracion)" ]; }
completo() {
    esperar 90 llego_restauracion || { echo "no llegó; recibido:"; docker logs "$id-buzon" 2>&1 | head -30; return 1; }
    local c
    c="$(el_de_restauracion)"
    for texto in "alertas@prueba.local" "La restauración de prueba falló" "verificar-restauracion.sh" "(critica)"; do
        grep -qF "$texto" <<< "$c" || { echo "falta «$texto» en:"; echo "$c"; return 1; }
    done
}
comprobar "va a la dirección configurada, dice qué pasó y qué hacer" completo

docker run -d --name "$id-grafana" --network "$id" -v "$raiz/infra/monitoreo/grafana/provisioning:/etc/grafana/provisioning:ro" \
    -v "$raiz/infra/monitoreo/grafana/paneles:/var/lib/medtender-paneles:ro" \
    -e GF_SECURITY_ADMIN_PASSWORD=clave-inventada -e GF_ANALYTICS_REPORTING_ENABLED=false \
    -e GF_ANALYTICS_CHECK_FOR_UPDATES=false -e GF_PLUGINS_PREINSTALL_DISABLED=true "$GRAF" > /dev/null
grafana() { docker exec "$id-grafana" wget -qO- "http://admin:clave-inventada@127.0.0.1:3000$1" 2> /dev/null; }
panel() { grafana '/api/dashboards/uid/medtender' | grep -q '"title":"MedTender"'; }
comprobar "Grafana carga el panel de MedTender" esperar 120 panel
datos() { grafana '/api/datasources/uid/prometheus/health' | grep -q '"status":"OK"'; }
comprobar "y llega a Prometheus" esperar 30 datos
sin_clave() { ! docker exec "$id-grafana" wget -qO- http://127.0.0.1:3000/api/dashboards/uid/medtender > /dev/null 2>&1; }
comprobar "sin contraseña no se ve nada" sin_clave

rm -rf "$copia"
if [ "$fallos" -ne 0 ]; then # para ver la causa en el registro de CI
    for servicio in prometheus alertmanager; do
        echo "--- registro de $servicio"
        docker logs "$id-$servicio" 2>&1 | tail -15
    done
fi
echo
if [ "$fallos" -eq 0 ]; then echo "Monitoreo: todas las comprobaciones pasaron"; else echo "Monitoreo: $fallos comprobación(es) fallaron"; fi
exit "$fallos"
