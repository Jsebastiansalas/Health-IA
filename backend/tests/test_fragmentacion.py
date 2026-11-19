"""Fragmentación de 500–1.000 tokens reales con solape ~15 % (sin base de datos)."""

from app.pipeline.fragmentacion import Fragmentador, cabecera_contextual, contar_tokens
from app.pipeline.modelos import (
    ConfigFragmentacion,
    FragmentoGenerado,
    MetodoExtraccion,
    PaginaExtraida,
    Parte,
)
from app.pipeline.tablas import a_markdown
from tests.pdfs import texto_largo

CFG = ConfigFragmentacion(min_tokens=500, max_tokens=1000, overlap_ratio=0.15)


def pagina(numero: int, *textos: str, metodo=MetodoExtraccion.NATIVE, conf=None, **kw):
    return PaginaExtraida(
        numero=numero,
        metodo=metodo,
        partes=[Parte(t) for t in textos],
        ocr_confidence=conf,
        **kw,
    )


def fragmentar(paginas) -> list[FragmentoGenerado]:
    return Fragmentador(CFG).fragmentar(paginas)


def _solapan(anterior: str, siguiente: str) -> bool:
    """El inicio del siguiente aparece en el tramo final del anterior."""
    inicio = siguiente[:60]
    return inicio in anterior[-int(len(anterior) * 0.4) :]


def test_rango_de_tokens_orden_y_solape():
    paginas = [pagina(n, texto_largo(60, tema=f"lote {n}")) for n in range(1, 6)]
    frags = fragmentar(paginas)

    assert len(frags) >= 5
    assert [f.orden for f in frags] == list(range(1, len(frags) + 1))
    for f in frags[:-1]:
        assert 500 <= f.token_count <= 1000, f.token_count
    assert frags[-1].token_count <= 1000
    for anterior, siguiente in zip(frags, frags[1:], strict=False):
        assert _solapan(anterior.texto, siguiente.texto)
        assert siguiente.pagina_inicio <= siguiente.pagina_fin
        assert siguiente.pagina_inicio >= anterior.pagina_inicio  # avanza


def test_solape_es_moderado():
    frags = fragmentar([pagina(1, texto_largo(200))])
    a, b = frags[0], frags[1]
    # Longitud del tramo común entre el final de a y el inicio de b.
    comun = max(n for n in range(1, len(b.texto)) if a.texto.endswith(b.texto[:n]) or n == 1)
    tokens_comunes = contar_tokens(b.texto[:comun])
    assert 0.05 * a.token_count <= tokens_comunes <= 0.20 * a.token_count


def test_paginas_de_cada_fragmento():
    frags = fragmentar(
        [pagina(1, texto_largo(30)), pagina(2, texto_largo(30)), pagina(3, texto_largo(30))]
    )
    assert frags[0].pagina_inicio == 1
    assert frags[-1].pagina_fin == 3
    assert any(f.pagina_inicio < f.pagina_fin for f in frags)  # al menos uno cruza páginas


def test_encabezado_abre_fragmento_sin_solape():
    paginas = [
        pagina(1, "CAPÍTULO 1 OBJETO DEL CONTRATO\n\n" + texto_largo(35)),
        pagina(2, "CLÁUSULA SEGUNDA - GARANTÍAS\n\n" + texto_largo(35, tema="garantías")),
    ]
    frags = fragmentar(paginas)
    segunda = next(f for f in frags if f.texto.startswith("CLÁUSULA SEGUNDA"))
    assert segunda.seccion == "CLÁUSULA SEGUNDA - GARANTÍAS"
    assert segunda.pagina_inicio == 2
    assert frags[0].seccion == "CAPÍTULO 1 OBJETO DEL CONTRATO"


def test_seccion_se_hereda_entre_paginas():
    paginas = [
        pagina(1, "ADENDA No. 2\n\n" + texto_largo(10)),
        pagina(2, texto_largo(80)),
    ]
    frags = fragmentar(paginas)
    assert all(f.seccion == "ADENDA No. 2" for f in frags)


def test_sin_encabezados_usa_seccion_por_defecto():
    assert fragmentar([pagina(1, "Texto corto sin encabezado.")])[0].seccion == "(sin sección)"


def test_documento_corto_es_un_solo_fragmento():
    frags = fragmentar([pagina(1, "Objeto: compra de jeringas."), pagina(2, "Plazo: 30 días.")])
    assert len(frags) == 1
    assert (frags[0].pagina_inicio, frags[0].pagina_fin) == (1, 2)
    assert frags[0].texto == "Objeto: compra de jeringas.\n\nPlazo: 30 días."


def test_cola_corta_se_une_al_anterior_si_cabe():
    # Sección A (~600 tokens) cierra fragmento al llegar la sección B, que es diminuta.
    paginas = [
        pagina(1, "CAPÍTULO 1 OBJETO\n\n" + texto_largo(25)),
        pagina(2, "ANEXO 1 FIRMAS\n\nFin del documento."),
    ]
    frags = fragmentar(paginas)
    assert len(frags) == 1
    assert frags[0].texto.endswith("Fin del documento.")
    assert frags[0].seccion == "CAPÍTULO 1 OBJETO / ANEXO 1 FIRMAS"
    assert frags[0].token_count <= 1000


def test_rango_se_respeta_para_cualquier_longitud():
    for n in range(5, 130, 11):
        frags = fragmentar([pagina(1, texto_largo(n))])
        assert all(500 <= f.token_count <= 1000 for f in frags[:-1]), n
        assert frags[-1].token_count <= 1000, n


def test_tabla_grande_se_parte_repitiendo_encabezado():
    filas = [["Código CUM", "Principio activo", "Concentración", "Precio"]]
    filas += [
        [f"1991{i:04d}-1", f"Medicamento genérico número {i}", "10 mg/ml", f"$ {i * 1000}"]
        for i in range(150)
    ]
    md = a_markdown(filas)
    frags = fragmentar(
        [PaginaExtraida(1, MetodoExtraccion.NATIVE, [Parte(md, es_tabla=True)], has_tables=True)]
    )

    assert len(frags) >= 2
    cabecera = "| Código CUM | Principio activo | Concentración | Precio |"
    for f in frags:
        assert f.metadata["has_tables"] is True
        assert f.token_count <= 1000
        assert cabecera in f.texto
    # Ninguna fila se pierde.
    juntos = "\n".join(f.texto for f in frags)
    assert all(f"1991{i:04d}-1" in juntos for i in range(150))


def test_oracion_gigante_se_trocea_por_tokens():
    sin_puntos = " ".join(f"palabra{i}" for i in range(3000))
    frags = fragmentar([pagina(1, sin_puntos)])
    assert all(f.token_count <= 1000 for f in frags)
    assert "palabra2999" in frags[-1].texto


def test_metadata_mixta_y_confianza_minima():
    paginas = [
        pagina(1, texto_largo(5)),
        pagina(2, texto_largo(5), metodo=MetodoExtraccion.OCR, conf=0.93, has_visual_elements=True),
        pagina(
            3,
            texto_largo(5),
            metodo=MetodoExtraccion.OCR,
            conf=0.71,
            has_signatures_or_stamps=True,
            has_visual_elements=True,
        ),
    ]
    m = fragmentar(paginas)[0].metadata
    assert m == {
        "extraction_method": "MIXED",
        "ocr_confidence": 0.71,
        "has_tables": False,
        "has_visual_elements": True,
        "has_signatures_or_stamps": True,
    }
    solo_ocr = fragmentar([pagina(1, "Texto escaneado.", metodo=MetodoExtraccion.OCR, conf=0.8)])
    assert solo_ocr[0].metadata["extraction_method"] == "OCR"


def test_token_especial_en_el_texto_no_rompe():
    frags = fragmentar([pagina(1, "Texto con <|endoftext|> literal en el PDF.")])
    assert "<|endoftext|>" in frags[0].texto


def test_paginas_vacias_no_generan_fragmentos():
    assert (
        fragmentar(
            [PaginaExtraida(1, MetodoExtraccion.NATIVE), PaginaExtraida(2, MetodoExtraccion.NATIVE)]
        )
        == []
    )


def test_cabecera_contextual():
    f = FragmentoGenerado(3, 24, 25, "CLÁUSULA 5", "El oferente...", 3, {})
    assert cabecera_contextual("LIC-2026-01", "Pliego.pdf", "PLIEGO", f) == (
        "[Expediente: LIC-2026-01 | Doc: Pliego.pdf | Tipo: PLIEGO | Pág: 24-25 | "
        "Sección: CLÁUSULA 5] El oferente..."
    )
