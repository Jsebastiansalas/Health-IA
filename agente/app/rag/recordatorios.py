# ruff: noqa: E501
"""Propuestas de recordatorio a partir de los controles que indican los documentos.

Toma de la línea de tiempo (sprint 37) los eventos de tipo CONTROL y propone una fecha:
- si el documento escribe la fecha («cita el 12/02/2026»), esa;
- si es relativa («control en 3 meses»), la fecha del documento que lo indica más ese plazo. La calcula
  este código, nunca el modelo; si el plazo no se entiende, la propuesta queda SIN fecha y la persona la
  pone.
Son solo propuestas: la persona confirma cada una antes de que exista un aviso. Nunca se proponen
recordatorios de tomas de medicamentos (eso sería dosificar).
"""

import re
from datetime import date, timedelta

from app.rag.cronologia import _norm

_NUMEROS = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "doce": 12,
}
_PLAZO = re.compile(
    r"\b(?:en|dentro de|despues de|a los?)\s+(?P<n>\d{1,3}|un|una|uno|dos|tres|cuatro|cinco|seis|doce)\s+"
    r"(?P<u>dias?|semanas?|mes(?:es)?|anos?)\b"
)
# Por si el modelo marca como «control» una toma de medicamento: eso no se recuerda.
_TOMA = re.compile(
    r"\b(?:tome|tomar|tomese|cada\s+\d+\s+horas?|tabletas?|capsulas?|gotas?|dosis)\b"
)


def _sumar_meses(base: date, meses: int) -> date:
    anio, mes = divmod(base.month - 1 + meses, 12)
    anio, mes = base.year + anio, mes + 1
    # 31 de enero + 1 mes → último día de febrero.
    for dia in (base.day, 30, 29, 28):
        try:
            return date(anio, mes, dia)
        except ValueError:
            continue
    return date(anio, mes, 28)


def fecha_por_plazo(texto: str, base: date) -> date | None:
    """«en 3 meses» desde `base`. None si el plazo no se entiende."""
    m = _PLAZO.search(_norm(texto))
    if not m:
        return None
    n = int(m["n"]) if m["n"].isdigit() else _NUMEROS[m["n"]]
    u = m["u"]
    if u.startswith("dia"):
        return base + timedelta(days=n)
    if u.startswith("semana"):
        return base + timedelta(weeks=n)
    if u.startswith("mes"):
        return _sumar_meses(base, n)
    return _sumar_meses(base, 12 * n)


def propuestas(linea: dict) -> list[dict]:
    """Los controles de la línea de tiempo como propuestas, cada una con su cita al documento."""
    citas = linea.get("citas") or []
    salida, vistas = [], set()
    for e in linea.get("eventos") or []:
        if e.get("tipo") != "CONTROL" or _TOMA.search(_norm(e.get("texto", ""))):
            continue
        # «Control en 3 meses» con la fecha del documento: el plazo se cuenta desde esa fecha (el
        # modelo a veces pone como fecha del control la del documento que lo indica).
        base = e.get("referencia") or e.get("fecha")
        plazo = f"{e.get('fechaTexto', '')} {e.get('texto', '')}"
        fecha = fecha_por_plazo(plazo, date.fromisoformat(base)) if base else None
        if fecha is None and e.get("fecha"):
            fecha = date.fromisoformat(e["fecha"])
        n = e.get("cita") or 0
        cita = citas[n - 1] if 0 < n <= len(citas) else None
        if cita is None:
            continue
        clave = (_norm(e.get("texto", "")), cita.get("documentoId"))
        if clave in vistas:
            continue
        vistas.add(clave)
        salida.append(
            {
                "texto": e["texto"],
                "fechaTexto": e.get("fechaTexto") or "",
                "fechaDocumento": base or e.get("fecha"),
                "fechaPropuesta": fecha.isoformat() if fecha else None,
                "cita": {
                    "documentoId": cita.get("documentoId"),
                    "nombreArchivo": cita.get("nombreArchivo"),
                    "paginaInicio": cita.get("paginaInicio"),
                    "extractoLiteral": cita.get("extractoLiteral"),
                },
            }
        )
    return salida
