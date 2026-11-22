"""Señales de alarma en la pregunta del usuario.

El asistente explica documentos y cita fuentes; no atiende urgencias. Si la pregunta describe algo
que puede ser una urgencia (dolor de pecho, falta de aire, una posible sobredosis, ideas de hacerse
daño…), la respuesta lleva SIEMPRE, antes que nada, un aviso para llamar al 123 o acudir a
urgencias, tanto si el modelo respondió como si se abstuvo.

Es una red de seguridad deliberadamente simple y sin modelo: reglas sobre el texto, sin acentos ni
mayúsculas. Prefiere el falso positivo (un aviso de más) al falso negativo (callar ante una
urgencia). Se aplica a la PREGUNTA, no a los documentos: un informe que menciona un dolor de pecho
de hace años no es una urgencia.
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Urgencia:
    codigo: str
    mensaje: str


_GENERAL = (
    "Si lo que describes está pasando ahora, no esperes una respuesta de este asistente: llama al "
    "123 o acude de inmediato al servicio de urgencias más cercano."
)

_RIESGO_VIDA = (
    "Lamento que estés pasando por esto. No tienes que enfrentarlo solo/a: llama ahora al 123 o "
    "acude a urgencias, y si puedes, cuéntaselo a una persona de confianza que esté cerca."
)

# Cada patrón se aplica al texto ya normalizado (minúsculas, sin acentos).
_REGLAS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "riesgo_vida",
        _RIESGO_VIDA,
        re.compile(
            r"\b(quiero morir(me)?|quitarme la vida|acabar con mi vida|suicid\w*|hacerme dano|"
            r"no quiero vivir|pensamientos de muerte)\b"
        ),
    ),
    (
        "pecho",
        _GENERAL,
        re.compile(r"\b(dolor|presion|opresion|apreton|punzada)\w* (en|del|de) (el |mi )?pecho\b"),
    ),
    (
        "respiracion",
        _GENERAL,
        re.compile(
            r"\b(no puedo respirar|dificultad (para|al) respirar|falta de (aire|aliento)|"
            r"me ahogo|ahogo|asfixia|labios morados)\b"
        ),
    ),
    (
        "sangrado",
        _GENERAL,
        re.compile(
            r"\b(sangrado (abundante|fuerte|que no para)|hemorragia|vomit\w* (con )?sangre|"
            r"sangre en (la |las )?(orina|heces|deposicion)|tos con sangre)\b"
        ),
    ),
    (
        "conciencia",
        _GENERAL,
        re.compile(
            r"\b(perdi(da)? (del )?conocimiento|desmayo|me desmaye|se desmayo|convulsion\w*|"
            r"ataque epileptico)\b"
        ),
    ),
    (
        "neurologico",
        _GENERAL,
        re.compile(
            r"\b(paralisis|cara torcida|no puedo mover|dificultad para hablar|"
            r"habla (arrastrada|enredada)|debilidad (repentina|subita)|perdida de la vision)\b"
        ),
    ),
    (
        "alergia_grave",
        _GENERAL,
        re.compile(
            r"\b(anafilaxia|reaccion alergica (grave|fuerte)|"
            r"(se me )?cierra(n)? (la )?garganta|garganta (cerrada|hinchada)|"
            r"hinchazon (de la |en la )?(garganta|lengua|cara)|"
            r"se me hincha (la )?(lengua|garganta))\b"
        ),
    ),
    (
        "intoxicacion",
        _GENERAL,
        re.compile(
            r"\b(sobredosis|intoxicacion|envenenamiento|me tome (muchas|demasiadas)|"
            r"(se|me) (tomo|tome) (todo|todas)|tome de mas)\b"
        ),
    ),
]


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_acentos.lower()).strip()


def detectar_urgencia(pregunta: str) -> Urgencia | None:
    """La señal más grave de la pregunta (el riesgo para la vida va primero), o `None`."""
    texto = _normalizar(pregunta)
    for codigo, mensaje, patron in _REGLAS:
        if patron.search(texto):
            return Urgencia(codigo, mensaje)
    return None


def con_urgencia(cuerpo: dict, pregunta: str) -> dict:
    """Añade `urgencia` al cuerpo y la pone como PRIMERA alerta. No modifica nada más."""
    urgencia = detectar_urgencia(pregunta)
    if urgencia is None:
        cuerpo["urgencia"] = None
        return cuerpo
    cuerpo["urgencia"] = {"codigo": urgencia.codigo, "mensaje": urgencia.mensaje}
    cuerpo["alertas"] = [urgencia.mensaje, *cuerpo.get("alertas", [])]
    return cuerpo
