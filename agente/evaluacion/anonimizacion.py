"""Mide la anonimización: cuántos nombres se escapan y cuántas palabras se tapan de más."""

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

_MARCA = re.compile(r"⟦(.+?)⟧", re.DOTALL)
_MARCADOR = re.compile(r"\[[A-Z]+_\d+\]")
_PALABRA = re.compile(r"[^\W\d_]+")


@dataclass
class Medida:
    nombres: int = 0
    escapados: list[tuple[str, str]] = field(default_factory=list)  # (nombre, texto enviado)
    palabras: int = 0  # palabras que no son parte de un nombre
    de_mas: list[tuple[list[str], str]] = field(default_factory=list)  # (palabras, texto enviado)

    @property
    def cobertura(self) -> float:
        return 1 - len(self.escapados) / self.nombres if self.nombres else 1.0

    @property
    def tapado_de_mas(self) -> float:
        return sum(len(p) for p, _ in self.de_mas) / self.palabras if self.palabras else 0.0


def _palabras(texto: str) -> Counter:
    return Counter(p.lower() for p in _PALABRA.findall(texto))


def medir(casos: list[str], enmascarar: Callable[[str], str]) -> Medida:
    """Un nombre se escapa si cualquiera de sus palabras (de 3 letras o más) sigue en el texto
    que saldría, aparte de las veces que esa palabra aparece fuera de los nombres."""
    m = Medida()
    for caso in casos:
        original = _MARCA.sub(r"\1", caso)
        fuera = _palabras(_MARCA.sub(" ", caso))
        enviado = enmascarar(original)
        quedan = _palabras(_MARCADOR.sub(" ", enviado))
        sobrantes = quedan - fuera
        for nombre in _MARCA.findall(caso):
            m.nombres += 1
            if any(len(p) >= 3 and sobrantes[p] for p in _palabras(nombre)):
                m.escapados.append((nombre, enviado))
        m.palabras += sum(fuera.values())
        perdidas = fuera - quedan
        if perdidas:
            m.de_mas.append((sorted(perdidas.elements()), enviado))
    return m


def informe(titulo: str, m: Medida) -> str:
    return (
        f"{titulo}: {m.nombres - len(m.escapados)}/{m.nombres} nombres ocultos "
        f"({m.cobertura:.0%}); {m.tapado_de_mas:.1%} de las demás palabras tapadas de más"
    )
