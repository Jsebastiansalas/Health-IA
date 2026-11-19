"""Conversión de tablas extraídas (lista de filas) a Markdown."""


def _celda(valor: str | None) -> str:
    if valor is None:
        return ""
    return " ".join(str(valor).split()).replace("|", "\\|")


def filas_limpias(filas: list[list[str | None]]) -> list[list[str]]:
    limpias = [[_celda(c) for c in fila] for fila in filas if fila]
    limpias = [f for f in limpias if any(f)]
    if not limpias:
        return []
    ancho = max(len(f) for f in limpias)
    return [f + [""] * (ancho - len(f)) for f in limpias]


def encabezado_markdown(cabecera: list[str]) -> str:
    return "| " + " | ".join(cabecera) + " |\n| " + " | ".join("---" for _ in cabecera) + " |"


def fila_markdown(fila: list[str]) -> str:
    return "| " + " | ".join(fila) + " |"


def a_markdown(filas: list[list[str | None]]) -> str:
    """La primera fila se toma como encabezado. Devuelve "" si la tabla está vacía."""
    limpias = filas_limpias(filas)
    if not limpias:
        return ""
    lineas = [encabezado_markdown(limpias[0])]
    lineas += [fila_markdown(f) for f in limpias[1:]]
    return "\n".join(lineas)
