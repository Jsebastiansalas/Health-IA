#!/bin/bash
# Publica el estado de los respaldos para Prometheus, como archivo de métricas que lee un node-exporter
# (solo su colector de archivos). Va en un volumen aparte (ESTADO_DIR): el exportador no ve las copias.
# Se usa con `source`; necesita BACKUP_DIR. Sin ESTADO_DIR no hace nada.

publicar_estado() {
    [ -n "${ESTADO_DIR:-}" ] || return 0
    local tmp
    mkdir -p "$ESTADO_DIR"
    tmp="$(mktemp "${ESTADO_DIR}/.respaldos.XXXXXX")"
    {
        # Sin una copia correcta no se publica la fecha: así suena «sin estado de respaldos».
        [ -f "${BACKUP_DIR}/ultimo_ok" ] \
            && echo "medtender_respaldo_ultimo_ok_timestamp_segundos $(cat "${BACKUP_DIR}/ultimo_ok")"
        if [ -n "${BACKUP_REMOTO:-}" ]; then
            echo "medtender_respaldo_remoto_configurado 1"
            echo "medtender_respaldo_remoto_ok_timestamp_segundos $(cat "${BACKUP_DIR}/remoto_ok" 2> /dev/null || echo 0)"
        else
            echo "medtender_respaldo_remoto_configurado 0"
        fi
        [ -f "${BACKUP_DIR}/restauracion_ok" ] \
            && echo "medtender_restauracion_ultimo_ok_timestamp_segundos $(cat "${BACKUP_DIR}/restauracion_ok")"
        if [ -f "${BACKUP_DIR}/restauracion_fallo" ]; then
            echo "medtender_restauracion_fallo 1"
        else
            echo "medtender_restauracion_fallo 0"
        fi
    } > "$tmp"
    chmod 644 "$tmp" # el exportador no corre como root
    mv "$tmp" "${ESTADO_DIR}/respaldos.prom" # de una vez: nunca se lee a medias
}
