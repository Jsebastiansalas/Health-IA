"""Cómo se puntúa cada respuesta. Funciones puras sobre el JSON que recibiría la pantalla."""

import re
import unicodedata

from evaluacion import casos


def normalizar(texto: str) -> str:
    """Sin tildes ni mayúsculas, con un solo espacio y la coma decimal igual que el punto."""
    sin = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    sin = re.sub(r"(?<=\d),(?=\d)", ".", sin.lower())
    return " ".join(sin.split())


def _cifras(texto: str | None) -> set[str]:
    """Cada cifra una sola vez, con punto decimal («13,2» y «13.2» son la misma)."""
    return set(re.findall(r"\d+(?:\.\d+)*", normalizar(texto or "")))


def _contiene(texto: str, aguja: str) -> bool:
    return normalizar(aguja) in normalizar(texto)


def puntuar_respuesta(caso: casos.Pregunta, cuerpo: dict, documentos: dict) -> tuple[bool, bool]:
    """(dice el dato, una cita del documento correcto lo contiene). Abstenerse no puntúa."""
    if cuerpo.get("sinEvidencia"):
        return False, False
    dice = any(_contiene(cuerpo.get("respuestaAnalitica"), d) for d in caso.datos)
    cita = any(
        c.get("documentoId") == documentos[caso.documento]
        and any(_contiene(c.get("extractoLiteral"), d) for d in caso.datos)
        for c in cuerpo.get("citas") or []
    )
    return dice, cita


def cifras_respaldadas(cuerpo: dict) -> tuple[int, int]:
    """Cuántas de las cifras que dice la respuesta están escritas en alguna de sus citas."""
    dichas = _cifras(cuerpo.get("respuestaAnalitica"))
    citadas: set = set()
    for c in cuerpo.get("citas") or []:
        citadas |= _cifras(c.get("extractoLiteral"))
    return len(dichas & citadas), len(dichas)


def puntuar_linea(cuerpo: dict) -> dict:
    """Aciertos sobre lo esperado y cuántos de los valores mostrados se esperaban."""
    mostrados = [
        (a["clave"], v["valor"], v["fecha"])
        for a in cuerpo.get("analitos") or []
        for v in a["valores"]
    ]
    esperados = {(v.clave, v.cifra, v.fecha) for v in casos.VALORES}
    eventos = {(e["tipo"], e["fecha"]) for e in cuerpo.get("eventos") or []}
    return {
        "valores": (len(esperados & set(mostrados)), len(esperados)),
        "sin_inventos": (sum(1 for m in mostrados if m in esperados), len(mostrados)),
        "eventos": (len({(e.tipo, e.fecha) for e in casos.EVENTOS} & eventos), len(casos.EVENTOS)),
        "faltan": [f"valor {x}" for x in sorted(esperados - set(mostrados))]
        + [
            f"evento {x}"
            for x in sorted({(e.tipo, e.fecha) for e in casos.EVENTOS} - eventos, key=str)
        ]
        + [f"inesperado {m}" for m in mostrados if m not in esperados],
    }


def puntuar_explicacion(cuerpo: dict) -> tuple[int, list[str]]:
    texto = " ".join(
        [h.get("texto", "") for h in cuerpo.get("hallazgos") or []]
        + [c.get("extractoLiteral", "") for c in cuerpo.get("citas") or []]
    )
    faltan = [x for x in casos.EXPLICACION_ESPERADA if not _contiene(texto, x)]
    return len(casos.EXPLICACION_ESPERADA) - len(faltan), faltan


def puntuar_preparacion(cuerpo: dict) -> tuple[int, int, list[str]]:
    faltan: list[str] = []
    total = 0
    for lista, esperados in casos.PREPARACION_ESPERADA.items():
        clave = "nombre" if lista == "medicamentos" else "texto"
        presentes = " | ".join(x.get(clave, "") for x in cuerpo.get(lista) or [])
        total += len(esperados)
        faltan += [f"{lista}: {x}" for x in esperados if not _contiene(presentes, x)]
    return total - len(faltan), total, faltan


def comparar(medidas: dict[str, float], minimos: dict[str, float]) -> list[str]:
    """Qué métricas quedaron por debajo de su mínimo, o dejaron de medirse."""
    avisos = []
    for nombre, minimo in minimos.items():
        if nombre not in medidas:
            avisos.append(f"{nombre}: no se midió (mínimo {minimo:.0%})")
        elif medidas[nombre] + 1e-9 < minimo:
            avisos.append(f"{nombre}: {medidas[nombre]:.0%}, por debajo del mínimo {minimo:.0%}")
    return avisos
