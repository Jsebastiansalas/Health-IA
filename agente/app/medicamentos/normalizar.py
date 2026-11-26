"""Normalización de texto y fechas de los conjuntos de datos de INVIMA."""

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_NO_ALFANUM = re.compile(r"[^a-z0-9]+")


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin tildes y con todo lo que no sea letra o dígito reducido a un espacio.

    Es la misma función para indexar y para buscar, de modo que «ACETAMINOFÉN 500 mg» y
    «acetaminofen 500mg» coinciden."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return _NO_ALFANUM.sub(" ", sin_tildes.casefold()).strip()


def limpiar(texto: str | None, maximo: int | None = None) -> str | None:
    """Texto sin espacios sobrantes; vacío se vuelve None. Corta al máximo de la columna."""
    if texto is None:
        return None
    t = " ".join(str(texto).split())
    if not t:
        return None
    return t[:maximo] if maximo else t


def fecha(valor: str | None) -> date | None:
    """Acepta MM/DD/AAAA (como publica INVIMA) y ISO (AAAA-MM-DD[THH:MM:SS])."""
    v = (valor or "").strip()
    if not v:
        return None
    for formato in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(v[:10], formato).date()
        except ValueError:
            continue
    return None


def numero(valor: str | None) -> Decimal | None:
    v = (valor or "").strip().replace(",", ".")
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None
