"""Enumeraciones de dominio. Los valores coinciden con los CHECK de la migración inicial."""

from enum import StrEnum


class RolGlobal(StrEnum):
    ADMIN_TENANT = "ADMIN_TENANT"
    JURIDICO = "JURIDICO"
    AUDITOR_MEDICO = "AUDITOR_MEDICO"
    BIOMEDICO = "BIOMEDICO"
    LECTOR = "LECTOR"


class Permiso(StrEnum):
    LECTOR = "LECTOR"
    EDITOR = "EDITOR"
    ADMIN = "ADMIN"

    @property
    def nivel(self) -> int:
        return {"LECTOR": 1, "EDITOR": 2, "ADMIN": 3}[self.value]


class PoliticaBorrado(StrEnum):
    INMEDIATO = "INMEDIATO"
    DIFERIDO_1H = "DIFERIDO_1H"


class TipoExpediente(StrEnum):
    LICITACION_MEDICAMENTOS = "LICITACION_MEDICAMENTOS"
    DOTACION_BIOMEDICA = "DOTACION_BIOMEDICA"
    AUDITORIA_CLINICA = "AUDITORIA_CLINICA"


class EstadoExpediente(StrEnum):
    ABIERTO = "ABIERTO"
    CERRADO = "CERRADO"
    ARCHIVADO = "ARCHIVADO"


class TipoDocumento(StrEnum):
    PLIEGO = "PLIEGO"
    ADENDA = "ADENDA"
    FICHA_TECNICA = "FICHA_TECNICA"
    REGISTRO_SANITARIO = "REGISTRO_SANITARIO"
    HISTORIA_CLINICA = "HISTORIA_CLINICA"
    PRESUPUESTO = "PRESUPUESTO"
    PROSPECTO = "PROSPECTO"


class FormatoDocumento(StrEnum):
    """Formato real del archivo recibido: decide cómo se lee y su extensión en el disco."""

    PDF = "PDF"
    JPG = "JPG"
    PNG = "PNG"
    HEIC = "HEIC"


class EstadoIndexacion(StrEnum):
    """Enum único de estados del pipeline, compartido por BD y UI.

    RECIBIDO -> VALIDANDO -> EN_COLA -> EXTRAYENDO_OCR -> FRAGMENTANDO -> VECTORIZANDO
             -> INDEXADO_PENDIENTE_PURGA (solo política DIFERIDO_1H) -> INDEXADO_Y_PURGADO
    Cualquier estado no final puede pasar a ERROR_PURGADO.
    """

    RECIBIDO = "RECIBIDO"
    VALIDANDO = "VALIDANDO"
    EN_COLA = "EN_COLA"
    EXTRAYENDO_OCR = "EXTRAYENDO_OCR"
    FRAGMENTANDO = "FRAGMENTANDO"
    VECTORIZANDO = "VECTORIZANDO"
    INDEXADO_PENDIENTE_PURGA = "INDEXADO_PENDIENTE_PURGA"
    INDEXADO_Y_PURGADO = "INDEXADO_Y_PURGADO"
    ERROR_PURGADO = "ERROR_PURGADO"

    @property
    def es_final(self) -> bool:
        return self in (EstadoIndexacion.INDEXADO_Y_PURGADO, EstadoIndexacion.ERROR_PURGADO)


class MotivoPurga(StrEnum):
    INDEXADO = "INDEXADO"
    ERROR_VALIDACION = "ERROR_VALIDACION"
    ERROR_PROCESAMIENTO = "ERROR_PROCESAMIENTO"
    TIMEOUT = "TIMEOUT"
    HUERFANO = "HUERFANO"
    DOCUMENTO_ELIMINADO = "DOCUMENTO_ELIMINADO"


# Roles que pueden crear expedientes nuevos.
ROLES_CREADORES = {
    RolGlobal.ADMIN_TENANT,
    RolGlobal.JURIDICO,
    RolGlobal.AUDITOR_MEDICO,
    RolGlobal.BIOMEDICO,
}
