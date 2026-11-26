"""Detección de encabezados de sección en pliegos, adendas y anexos."""

import re

SIN_SECCION = "(sin sección)"
_MAX_LARGO_ENCABEZADO = 150
_MAX_LARGO_CON_IDENTIFICADOR = 90

_PALABRAS = (
    r"CAP[IÍ]TULO",
    r"NUMERAL",
    r"CL[AÁ]USULA",
    r"ADENDA",
    r"SECCI[OÓ]N",
    r"FICHA\s+T[EÉ]CNICA",
    r"ANTECEDENTES",
    r"ANEXO",
    r"ART[IÍ]CULO",
)
_PATRON = re.compile(rf"^(?:{'|'.join(_PALABRAS)})\b", re.IGNORECASE)

# Lo que identifica a un encabezado: "5", "5.2.1", "III", "No. 2", "PRIMERA", "A".
_IDENTIFICADOR = re.compile(
    r"^(?:\d+(?:\.\d+)*|[IVXLCDM]+|N[oº°]\.?\s*\d+|"
    r"PRIMER[OA]?|SEGUND[OA]|TERCER[OA]?|CUART[OA]|QUINT[OA]|SEXT[OA]|S[EÉ]PTIM[OA]|"
    r"OCTAV[OA]|NOVEN[OA]|D[EÉ]CIM[OA]|[A-Z])\b",
    re.IGNORECASE,
)


def es_encabezado(linea: str) -> bool:
    """Línea corta que empieza por una palabra clave de estructura y además:
    - está mayoritariamente en mayúsculas ("FICHA TÉCNICA DEL EQUIPO"), o
    - lleva un identificador tras la palabra clave ("Cláusula 5. Garantías", "Anexo A"), o
    - es solo la palabra clave ("Antecedentes").

    Así no se toma como encabezado una línea de texto corrido que, por el ajuste de línea del
    PDF, empieza con "ficha técnica del equipo..." o "Anexo técnico deberá...".
    """
    linea = linea.strip()
    if not 0 < len(linea) <= _MAX_LARGO_ENCABEZADO or not linea[0].isupper():
        return False
    coincidencia = _PATRON.match(linea)
    if not coincidencia:
        return False

    letras = [c for c in linea if c.isalpha()]
    if sum(c.isupper() for c in letras) / len(letras) >= 0.6:
        return True
    resto = linea[coincidencia.end() :].lstrip(" .:-–")
    if not resto:
        return True
    return len(linea) <= _MAX_LARGO_CON_IDENTIFICADOR and bool(_IDENTIFICADOR.match(resto))


def normalizar_titulo(linea: str) -> str:
    return " ".join(linea.split())[:255]
