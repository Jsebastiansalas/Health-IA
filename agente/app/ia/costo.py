"""Costo de la IA generativa: tokens por llamada, costo estimado y tope diario.

Cada respuesta del modelo trae cuántos tokens leyó y escribió. Con la tabla de precios se estima
lo que costó, se suma al gasto del día (hora de Colombia) y se publica en las métricas. Si el
gasto llega al tope diario configurado, las siguientes llamadas se rechazan hasta el otro día:
la persona ve «el servicio de IA no está disponible» en lugar de una factura sorpresa.

Límites conocidos:
- El contador vive en la memoria del proceso de la API (el único que llama al modelo
  generativo). Si el agente se reinicia, el gasto del día vuelve a cero; la métrica
  `medtender_ia_costo_usd_total` sigue siendo la referencia para las alertas.
- Los embeddings no entran: sus respuestas no traen tokens y cuestan una fracción del resto.
- Los precios son de referencia y cambian; se ajustan con `IA_PRECIOS` sin tocar el código.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone

from app.core.metricas import IA_COSTO, IA_COSTO_HOY, IA_TOKENS, IA_TOPE_RECHAZOS

log = logging.getLogger(__name__)

COLOMBIA = timezone(timedelta(hours=-5))  # sin horario de verano

# US$ por millón de tokens (entrada, salida). Referencia de noviembre de 2026; en Gemini los
# tokens de razonamiento se cobran como salida.
PRECIOS_REFERENCIA: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
# Un modelo sin precio conocido se cuenta caro, para que el tope no se quede corto.
PRECIO_DESCONOCIDO = (4.00, 20.00)


class TopeDiarioAlcanzado(Exception):
    pass


@dataclass(frozen=True)
class Uso:
    entrada: int
    salida: int


def _hoy() -> date:
    return datetime.now(UTC).astimezone(COLOMBIA).date()


@dataclass
class ControlDeCosto:
    tope_diario_usd: float = 0.0  # 0 = sin tope
    precios: dict[str, tuple[float, float]] = field(default_factory=dict)
    _dia: date | None = None
    _gasto: float = 0.0

    def precio(self, modelo: str) -> tuple[float, float]:
        return self.precios.get(modelo) or PRECIOS_REFERENCIA.get(modelo) or PRECIO_DESCONOCIDO

    def costo(self, modelo: str, uso: Uso) -> float:
        entrada, salida = self.precio(modelo)
        return (uso.entrada * entrada + uso.salida * salida) / 1_000_000

    def gasto_hoy(self) -> float:
        if self._dia != _hoy():
            self._dia, self._gasto = _hoy(), 0.0
            IA_COSTO_HOY.set(0)
        return self._gasto

    def verificar(self) -> None:
        """Antes de cada llamada: con el tope alcanzado no se llama al proveedor."""
        if self.tope_diario_usd > 0 and self.gasto_hoy() >= self.tope_diario_usd:
            IA_TOPE_RECHAZOS.inc()
            raise TopeDiarioAlcanzado(
                f"Tope diario de IA alcanzado (US$ {self.gasto_hoy():.2f} de "
                f"US$ {self.tope_diario_usd:.2f})"
            )

    def registrar(self, proveedor: str, modelo: str, uso: Uso | None) -> float:
        if uso is None:
            return 0.0
        costo = self.costo(modelo, uso)
        self._gasto = self.gasto_hoy() + costo
        IA_TOKENS.labels(proveedor, modelo, "entrada").inc(uso.entrada)
        IA_TOKENS.labels(proveedor, modelo, "salida").inc(uso.salida)
        IA_COSTO.labels(proveedor, modelo).inc(costo)
        IA_COSTO_HOY.set(self._gasto)
        # Solo cifras: nunca el contenido de la llamada.
        log.info(
            "IA %s/%s: %d tokens de entrada, %d de salida, US$ %.5f (hoy US$ %.4f)",
            proveedor,
            modelo,
            uso.entrada,
            uso.salida,
            costo,
            self._gasto,
        )
        return costo
