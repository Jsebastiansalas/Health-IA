"""Modelos ORM. El esquema canónico vive en alembic/versions/0001_init_schema.py."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1536


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = _pk()
    nombre: Mapped[str] = mapped_column(String(150))
    nit: Mapped[str] = mapped_column(String(50), unique=True)
    politica_borrado: Mapped[str] = mapped_column(String(30), server_default="INMEDIATO")
    created_at: Mapped[datetime] = _created_at()


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    nombre_completo: Mapped[str] = mapped_column(String(150))
    rol_global: Mapped[str] = mapped_column(String(40))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = _created_at()


class Expediente(Base):
    __tablename__ = "expedientes"

    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    codigo_expediente: Mapped[str] = mapped_column(String(80))
    titulo: Mapped[str] = mapped_column(String(250))
    entidad_contratante: Mapped[str | None] = mapped_column(String(200))
    tipo_expediente: Mapped[str] = mapped_column(String(50))
    estado: Mapped[str] = mapped_column(String(40), server_default="ABIERTO")
    embedding_model_activo: Mapped[str] = mapped_column(
        String(80), server_default="text-embedding-3-small"
    )
    embedding_dimension: Mapped[int] = mapped_column(Integer, server_default="1536")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = _created_at()


class ExpedientePermiso(Base):
    __tablename__ = "expediente_permisos"

    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expedientes.id", ondelete="CASCADE")
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    permiso: Mapped[str] = mapped_column(String(30))


class Documento(Base):
    __tablename__ = "documentos"

    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expedientes.id", ondelete="CASCADE")
    )
    nombre_archivo_original: Mapped[str] = mapped_column(String(255))
    tipo_documento: Mapped[str] = mapped_column(String(50))
    numero_adenda: Mapped[int | None] = mapped_column(Integer, server_default="0")
    sha256_original: Mapped[str] = mapped_column(String(64))
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    total_paginas: Mapped[int | None] = mapped_column(Integer)
    estado_indexacion: Mapped[str] = mapped_column(String(40))
    ocr_version: Mapped[str] = mapped_column(String(30), server_default="tesseract-5.x-v1")
    extractor_version: Mapped[str] = mapped_column(
        String(30), server_default="pymupdf-pdfplumber-v1"
    )
    embedding_model: Mapped[str] = mapped_column(String(80))
    total_chunks_esperados: Mapped[int | None] = mapped_column(Integer, server_default="0")
    total_chunks_guardados: Mapped[int | None] = mapped_column(Integer, server_default="0")
    temp_file_purged: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Sprint 2 (migración 0002)
    motivo_error: Mapped[str | None] = mapped_column(Text)
    purga_programada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado_actualizado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ActaPurga(Base):
    """Registro auditable de cada borrado de un PDF temporal."""

    __tablename__ = "actas_purga"

    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id"))
    documento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documentos.id", ondelete="SET NULL")
    )
    sha256_original: Mapped[str | None] = mapped_column(String(64))
    motivo: Mapped[str] = mapped_column(String(30))
    chunks_esperados: Mapped[int | None] = mapped_column(Integer)
    chunks_verificados: Mapped[int | None] = mapped_column(Integer)
    archivo_existia: Mapped[bool] = mapped_column(Boolean)
    detalle: Mapped[str | None] = mapped_column(Text)
    purged_at: Mapped[datetime] = _created_at()


class Fragmento(Base):
    __tablename__ = "fragmentos"

    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expedientes.id", ondelete="CASCADE")
    )
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documentos.id", ondelete="CASCADE"))
    orden: Mapped[int] = mapped_column(Integer)
    pagina_inicio: Mapped[int] = mapped_column(Integer)
    pagina_fin: Mapped[int] = mapped_column(Integer)
    seccion: Mapped[str] = mapped_column(String(255))
    contenido_texto: Mapped[str] = mapped_column(Text)
    contenido_vectorizado: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(80))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    fts_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('spanish', coalesce(seccion, '') || ' ' || coalesce(contenido_texto, ''))",
            persisted=True,
        ),
    )
    metadata_jsonb: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = _created_at()
