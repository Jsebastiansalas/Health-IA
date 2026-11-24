# ruff: noqa: E501
"""Comprobaciones deterministas sobre lo que devuelve el modelo (sin llamar a otro modelo).

Dos garantías que no dependen de que el prompt se respete:
1. Una afirmación del modelo no puede traer cifras ni juicios («alto», «grave», «anormal»…) que el
   fragmento citado no contenga. Una paráfrasis que añade un número o un veredicto se descarta.
2. Ninguna respuesta puede traer una posología («500 mg cada 8 horas», «tome 2…») que no esté escrita
   en un extracto citado: la dosis nunca sale del conocimiento del modelo.

Son reglas simples: prefieren descartar de más a dejar pasar de menos. No sustituyen la cita literal que
la interfaz muestra al lado de cada afirmación.
"""

import re
import unicodedata

from app.rag import seguridad


def _norm(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin.lower()).strip()


_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def numeros(texto: str) -> set[str]:
    """Las cifras de un texto en dos formas (con el decimal normalizado y solo dígitos), para que
    «13,2», «13.2» y «1.020.304.050» se comparen sin importar el formato."""
    salida: set[str] = set()
    for m in _NUM.findall(_norm(texto)):
        salida.add(m.replace(",", "."))
        salida.add(re.sub(r"\D", "", m))
    return salida


# Juicios que solo valen si el propio fragmento los dice: «el valor está alto», «es normal»…
_JUICIO = re.compile(
    r"\b(?:es|esta|estan|son|resulto|salio|nivel|valor|valores|resultado|dentro de lo|muy|ligeramente)"
    r"\s+(?:muy\s+|ligeramente\s+)?(?P<j>alt[oa]s?|baj[oa]s?|elevad[oa]s?|anormal(?:es)?|grave|"
    r"peligros[oa]|preocupante|normal(?:es)?|bueno|malo|sano|saludable)\b"
)
_RAIZ = {
    "alt": "alt",
    "baj": "baj",
    "elevad": "elevad",
    "anormal": "anormal",
    "grave": "grave",
    "peligros": "peligros",
    "preocupante": "preocupant",
    "normal": "normal",
    "bueno": "buen",
    "malo": "mal",
    "sano": "san",
    "saludable": "saludable",
}


def _raiz(j: str) -> str:
    for clave, raiz in _RAIZ.items():
        if j.startswith(clave):
            return raiz
    return j


def afirma_sin_respaldo(afirmacion: str, fragmento: str) -> bool:
    """Verdadero si la afirmación trae una cifra o un juicio que el fragmento citado no contiene.

    «El rango normal es 12,0 a 15,5» pasa (es un rango, no un veredicto sobre la persona) siempre que
    las cifras estén en el fragmento; «el colesterol está alto» solo pasa si el fragmento lo dice."""
    en_fragmento = numeros(fragmento)
    if any(n not in en_fragmento for n in numeros(afirmacion)):
        return True
    f = _norm(fragmento)
    return any(_raiz(m.group("j")) not in f for m in _JUICIO.finditer(_norm(afirmacion)))


_UNIDAD = r"(?:mg|mcg|ug|g|ml|gotas?|tabletas?|comprimidos?|capsulas?|pastillas?|ampollas?|sobres?|ui|unidades)"
_POSOLOGIA = re.compile(
    rf"\b\d+(?:[.,]\d+)?\s?{_UNIDAD}\b[^.\n]{{0,40}}\b(?:cada|al dia|por dia|diari\w*|\d+ veces|"
    r"veces al dia|dos veces|una vez|tres veces)\b"
    rf"|\b(?:tome|tomar|tomese|administre|aplique|inyecte|use|usar|ingiera)\b[^.\n]{{0,25}}\d+(?:[.,]\d+)?\s?{_UNIDAD}\b"
    r"|\b(?:una|dos|tres|cuatro|\d+)\s+(?:tabletas?|comprimidos?|capsulas?|pastillas?|gotas?)\s+"
    r"(?:cada|al dia|por dia|diari\w*)\b"
)


def posologia_sin_respaldo(texto: str, extractos: list[str]) -> bool:
    """Verdadero si el texto indica una posología cuyas cifras no están en ningún extracto citado."""
    t = _norm(texto)
    permitidas = set().union(*(numeros(e) for e in extractos)) if extractos else set()
    normalizados = [_norm(e) for e in extractos]
    for m in _POSOLOGIA.finditer(t):
        cifras = numeros(m.group(0))
        # Sin cifras («una tableta cada 12…» ya las trae; «una tableta cada día» no): debe estar escrito igual.
        respaldada = cifras <= permitidas if cifras else any(m.group(0) in e for e in normalizados)
        if not respaldada:
            return True
    return False


def sin_posologia_inventada(cuerpo: dict) -> dict:
    """Si la respuesta de la consola o de medicamentos indica una dosis que ningún extracto citado
    respalda, se sustituye por el mensaje de límite clínico (la dosis nunca sale del modelo)."""
    extractos = [c.get("extractoLiteral") or "" for c in cuerpo.get("citas", [])]
    if posologia_sin_respaldo(str(cuerpo.get("respuestaAnalitica") or ""), extractos):
        mensaje = next(m for c, m, _ in seguridad._LIMITES if c == "dosis")
        cuerpo["respuestaAnalitica"] = mensaje
        cuerpo["limiteClinico"] = {"codigo": "dosis", "origen": "salida"}
        cuerpo["sinEvidencia"] = True
        cuerpo["citas"] = []
    return cuerpo


_IMPERATIVO = re.compile(
    r"^(?:se\s+le\s+indica\s+que\s+)?(debe|debes|tiene\s+que|tienes\s+que|se\s+debe)\b",
    re.IGNORECASE,
)


def atribuir_al_documento(texto: str) -> str:
    """Un hallazgo no puede sonar a orden del asistente («Debe tomar…»): se presenta como lo que dice el
    documento («El documento indica que debe tomar…»)."""
    t = texto.strip()
    if _IMPERATIVO.match(t):
        return "El documento indica que " + t[0].lower() + t[1:]
    return t
