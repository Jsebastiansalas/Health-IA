import uuid
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.enums import (
    EstadoExpediente,
    EstadoIndexacion,
    MotivoPurga,
    Permiso,
    PoliticaBorrado,
    RolGlobal,
    TipoDocumento,
    TipoExpediente,
)


def _validar_password(v: str) -> str:
    # bcrypt solo procesa 72 bytes; rechazamos en vez de truncar en silencio.
    if len(v.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return v


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class RegistroTenantIn(BaseModel):
    tenant_nombre: str = Field(min_length=2, max_length=150)
    nit: str = Field(min_length=3, max_length=50)
    politica_borrado: PoliticaBorrado = PoliticaBorrado.INMEDIATO
    admin_email: EmailStr
    admin_password: str = Field(min_length=10)
    admin_nombre: str = Field(min_length=2, max_length=150)

    _pw = field_validator("admin_password")(_validar_password)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------- Tenant ----------
class TenantOut(ORMModel):
    id: uuid.UUID
    nombre: str
    nit: str
    politica_borrado: PoliticaBorrado
    created_at: datetime


class TenantUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    politica_borrado: PoliticaBorrado | None = None


# ---------- Usuarios ----------
class UsuarioOut(ORMModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    nombre_completo: str
    rol_global: RolGlobal
    activo: bool
    created_at: datetime


class UsuarioCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    nombre_completo: str = Field(min_length=2, max_length=150)
    rol_global: RolGlobal

    _pw = field_validator("password")(_validar_password)


class UsuarioUpdate(BaseModel):
    nombre_completo: str | None = Field(default=None, min_length=2, max_length=150)
    rol_global: RolGlobal | None = None
    activo: bool | None = None


# ---------- Expedientes ----------
class ExpedienteCreate(BaseModel):
    codigo_expediente: str = Field(min_length=1, max_length=80)
    titulo: str = Field(min_length=1, max_length=250)
    entidad_contratante: str | None = Field(default=None, max_length=200)
    tipo_expediente: TipoExpediente


class ExpedienteUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=250)
    entidad_contratante: str | None = Field(default=None, max_length=200)
    tipo_expediente: TipoExpediente | None = None
    estado: EstadoExpediente | None = None


class ExpedienteOut(ORMModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    codigo_expediente: str
    titulo: str
    entidad_contratante: str | None
    tipo_expediente: TipoExpediente
    estado: EstadoExpediente
    embedding_model_activo: str
    embedding_dimension: int
    created_by: uuid.UUID
    created_at: datetime
    mi_permiso: Permiso | None = None


# ---------- Documentos ----------
class DocumentoMetadatos(BaseModel):
    """Campos de texto que acompañan al PDF en el multipart."""

    tipo_documento: TipoDocumento
    numero_adenda: int = Field(default=0, ge=0, le=999)

    @model_validator(mode="after")
    def _adenda_coherente(self) -> "DocumentoMetadatos":
        if self.tipo_documento == TipoDocumento.ADENDA and self.numero_adenda < 1:
            raise ValueError("Una ADENDA requiere numero_adenda >= 1")
        if self.tipo_documento != TipoDocumento.ADENDA and self.numero_adenda != 0:
            raise ValueError("numero_adenda solo aplica a documentos tipo ADENDA")
        return self


class ActaPurgaOut(ORMModel):
    id: uuid.UUID
    motivo: MotivoPurga
    sha256_original: str | None
    chunks_esperados: int | None
    chunks_verificados: int | None
    archivo_existia: bool
    detalle: str | None
    purged_at: datetime


class DocumentoOut(ORMModel):
    id: uuid.UUID
    expediente_id: uuid.UUID
    nombre_archivo_original: str
    tipo_documento: TipoDocumento
    numero_adenda: int | None
    sha256_original: str
    tamano_bytes: int
    total_paginas: int | None
    estado_indexacion: EstadoIndexacion
    motivo_error: str | None
    embedding_model: str
    ocr_version: str
    extractor_version: str
    total_chunks_esperados: int | None
    total_chunks_guardados: int | None
    temp_file_purged: bool
    uploaded_at: datetime
    estado_actualizado_at: datetime
    purga_programada_at: datetime | None
    purged_at: datetime | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progreso(self) -> int:
        from app.services.estados import PROGRESO

        return PROGRESO[self.estado_indexacion]


class DocumentoDetalleOut(DocumentoOut):
    actas_purga: list[ActaPurgaOut] = []


# ---------- Permisos ----------
class PermisoIn(BaseModel):
    permiso: Permiso


class PermisoOut(ORMModel):
    usuario_id: uuid.UUID
    email: str
    nombre_completo: str
    permiso: Permiso
