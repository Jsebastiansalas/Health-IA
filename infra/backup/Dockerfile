# Respaldos: las herramientas de PostgreSQL de la misma versión que la base, y rclone (del repositorio de
# Debian) para la copia fuera del equipo. Los scripts se montan desde infra/backup.
FROM pgvector/pgvector:pg16

RUN apt-get update \
    && apt-get install -y --no-install-recommends rclone ca-certificates \
    && rm -rf /var/lib/apt/lists/*
