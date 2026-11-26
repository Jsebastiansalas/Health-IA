"""Depura el comparador del cruce con Gemini real: muestra qué devuelve el modelo y qué guardia descarta cada advertencia."""

import asyncio

from app.core.db import get_sessionmaker
from app.ia.llm import get_llm
from app.medicamentos import fichas
from app.rag import cruce, garantias


async def main():
    async with get_sessionmaker()() as s:
        todas = await fichas.fichas_de(s, "ibuprofeno", 6)
    meds = [{"nombre": "Ibuprofeno 400 mg", "principio_activo": "ibuprofeno", "cita": 1}]
    diags = [{"texto": "ulcera gastrica", "cita": 2}]
    alergias = [{"texto": "penicilina", "cita": 3}]
    print("secciones:", [(f["seccion"], len(f["texto"])) for f in todas])
    salida = await get_llm().generar_json(
        cruce.SISTEMA_CRUZAR,
        cruce._prompt_cruzar(meds, diags, alergias, todas),
        cruce.ESQUEMA_CRUZAR,
    )
    adv, omitidas = cruce.ensamblar_advertencias(salida.datos, meds, diags, alergias, todas)
    print("CONSERVADAS:", len(adv), "OMITIDAS:", omitidas)
    for x in adv:
        print("  *", x["texto"][:230])
    for a in salida.datos.get("advertencias", []):
        ficha = {f"F{i}": f for i, f in enumerate(todas, 1)}.get(cruce._id(a.get("ficha")))
        texto = cruce._sin_ids(
            cruce._t(a.get("texto")),
            {"M1": "Ibuprofeno 400 mg", "D1": "ulcera gastrica", "A1": "penicilina", "F1": "ficha"},
        )
        print("-", texto[:200])
        if ficha:
            resp = " ".join([ficha["texto"], "ulcera gastrica", "penicilina", "Ibuprofeno 400 mg"])
            print(
                "   numeros sin respaldo:",
                [n for n in garantias.numeros(texto) if n not in garantias.numeros(resp)],
            )
            from app.rag.garantias import _JUICIO, _norm, _raiz

            print(
                "   juicios sin respaldo:",
                [
                    m.group("j")
                    for m in _JUICIO.finditer(_norm(texto))
                    if _raiz(m.group("j")) not in _norm(resp)
                ],
            )
            print("   posologia:", garantias.posologia_sin_respaldo(texto, [ficha["texto"]]))


asyncio.run(main())
