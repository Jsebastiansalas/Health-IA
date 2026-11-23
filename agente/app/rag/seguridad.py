# ruff: noqa: E501
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
            r"me falta(n)? (el )?(aire|aliento)|falta el aire|(me )?cuesta (trabajo )?respirar|"
            r"respir\w* (mal|con dificultad)|no respiro|sin aliento|"
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


# ---------- Lo que el asistente nunca decide: dosis, qué tomar o recetar, diagnóstico ----------
@dataclass(frozen=True)
class LimiteClinico:
    codigo: str
    mensaje: str


_DERIVAR = (
    " Lo que sí puedo hacer: explicarte qué dicen tus documentos (con cita), contarte los efectos, "
    "contraindicaciones e interacciones de un medicamento concreto según su ficha técnica o prospecto, "
    "y ayudarte a preparar las preguntas para tu médico o farmacéutico."
)

_LIMITES: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "dosis",
        "No puedo indicar dosis ni decirte cuánto o cada cuánto tomar un medicamento: depende de cada "
        "persona y solo la define tu médico o tu farmacéutico." + _DERIVAR,
        re.compile(
            r"\b(que|cual) (es la |seria la )?dosis (me|debo|puedo|tomo|tomar|usar|uso|correcta|"
            r"adecuada|segura|maxima)|"
            r"\b(cuanto|cuanta|cuantos|cuantas) \w*\s?(me )?(tomo|tomar|debo tomar|puedo tomar|"
            r"inyecto|aplico|debo darle|le doy)\b|"
            r"\b(cada cuanto|cuantas veces al dia) (me |debo |puedo )?(tomo|tomar|tomarlo|inyecto)\b|"
            r"\bdosis (para|de) (un )?(nino|bebe|nina|adulto mayor)\b"
        ),
    ),
    (
        "receta",
        "No puedo decirte qué medicamento tomar, recetarte ni elegir uno según tu caso: esa decisión "
        "es de tu médico o tu farmacéutico, que conocen tu historia." + _DERIVAR,
        re.compile(
            r"\b(que|cual) (pastillas?|medicamentos?|medicinas?|antibioticos?|analgesicos?|remedios?|"
            r"tabletas?|jarabes?) (me )?(tomo|tomar|debo tomar|puedo tomar|deberia tomar|me conviene|"
            r"me sirve|me receto|me recetas|se pueden tomar|puedo usar|me puedo tomar)\b|"
            r"\b(recetame|formulame|recomiendame (un|una|algun|alguna) ?\w*)\b|"
            r"\bdime que (me )?(tomo|tomar)\b|\bque me tomo\b|\bque me puedo tomar\b"
        ),
    ),
    (
        "diagnostico",
        "No puedo diagnosticar ni decirte qué enfermedad tienes: solo un profesional que te valore "
        "puede hacerlo." + _DERIVAR,
        re.compile(
            r"\b(diagnosticame|diagnostico para mi|que enfermedad tengo|que tengo yo|de que estoy enfermo|"
            r"de que estoy enferma|que me pasa)\b"
        ),
    ),
]


_DOSIS_ESTRICTO = re.compile(r"\b(dosis|posologia|dosificacion|miligramos que)\b")


def detectar_limite_clinico(pregunta: str, estricto: bool = False) -> LimiteClinico | None:
    """Si la pregunta le pide al asistente decidir una dosis, un medicamento o un diagnóstico, el
    límite y su mensaje fijo. Sin modelo: la negativa no depende de que el prompt se respete.

    `estricto` (consulta de medicamentos, donde no hay un documento que contenga la indicación):
    cualquier mención de dosis o posología se rechaza."""
    texto = _normalizar(pregunta)
    for codigo, mensaje, patron in _LIMITES:
        if patron.search(texto):
            return LimiteClinico(codigo, mensaje)
    if estricto and _DOSIS_ESTRICTO.search(texto):
        return LimiteClinico("dosis", _LIMITES[0][1])
    return None


def cuerpo_de_limite(limite: LimiteClinico, consulta_id, modelo_embeddings: str | None) -> dict:
    """Respuesta fija con la forma pública de una consulta, sin modelo ni citas."""
    return {
        "consultaId": str(consulta_id),
        "respuestaAnalitica": limite.mensaje,
        "limiteClinico": {"codigo": limite.codigo},
        "sinEvidencia": True,
        "alertas": [],
        "citas": [],
        "modeloEmbeddings": modelo_embeddings,
        "modeloLlm": None,
        "fragmentosRecuperados": 0,
        "latenciaMs": 0,
    }
