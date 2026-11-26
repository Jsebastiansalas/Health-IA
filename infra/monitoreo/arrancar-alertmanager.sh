#!/bin/sh
# Escribe la configuración de Alertmanager con el correo del entorno (usa el mismo SMTP de la API) y lo arranca.
set -eu
: "${ALERTAS_CORREO:?defina ALERTAS_CORREO: a quién llegan las alertas}"
: "${SMTP_HOST:?defina SMTP_HOST}"

# Entre comillas simples de YAML, una comilla simple se escribe doble.
y() { printf '%s' "$1" | sed "s/'/''/g"; }

umask 077
{
    cat <<EOF
global:
  smtp_smarthost: '$(y "${SMTP_HOST}:${SMTP_PORT:-587}")'
  smtp_from: '$(y "${CORREO_REMITENTE:-no-responder@medtender.local}")'
  smtp_require_tls: ${SMTP_REQUIERE_TLS:-true}
EOF
    if [ -n "${SMTP_USER:-}" ]; then
        printf '%s' "${SMTP_PASSWORD:-}" > /tmp/smtp_password
        cat <<EOF
  smtp_auth_username: '$(y "$SMTP_USER")'
  smtp_auth_password_file: /tmp/smtp_password
EOF
    fi
    cat <<EOF

route:
  receiver: correo
  group_by: [alertname]
  group_wait: ${ESPERA_DE_AGRUPACION:-30s}
  group_interval: 5m
  repeat_interval: 12h
  routes:
    - matchers: ['severity="critica"']
      receiver: correo
      repeat_interval: 4h

receivers:
  - name: correo
    email_configs:
      - to: '$(y "$ALERTAS_CORREO")'
        send_resolved: true
        headers:
          Subject: 'MedTender [{{ .Status }}] {{ .CommonLabels.alertname }}'
        # Solo texto, y solo el resumen y el qué hacer de cada alerta.
        html: ''
        text: |
          {{ range .Alerts }}{{ if eq .Status "resolved" }}RESUELTO: {{ end }}{{ .Annotations.resumen }}
          Qué hacer: {{ .Annotations.que_hacer }}
          Alerta: {{ .Labels.alertname }} ({{ .Labels.severity }}) desde {{ .StartsAt.Format "2006-01-02 15:04 UTC" }}

          {{ end }}
EOF
} > /tmp/alertmanager.yml

exec /bin/alertmanager --config.file=/tmp/alertmanager.yml --storage.path=/alertmanager
