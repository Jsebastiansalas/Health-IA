"""Glosario curado: calidad del contenido (neutro, sin dosis ni veredictos) y búsqueda en el texto."""

import re

import pytest

from app.medicamentos.normalizar import normalizar
from app.rag import garantias, glosario
from app.rag.glosario_datos import COMUNES, ENTRADAS, GLOSARIO_REVISADO

# Palabras que convertirían una definición general en un veredicto sobre la persona o en una indicación.
PROHIBIDAS = re.compile(
    r"\b(debe|debes|deber[ií]a|tome|tomar|tomese|recomiend\w*|se recomienda|diagnostic[oó] de|"
    r"padece|sufre|usted tiene|tienes|cura|curar|tratamiento con)\b",
    re.IGNORECASE,
)


def test_el_glosario_tiene_cobertura_suficiente_y_declara_que_falta_la_revision():
    assert len(ENTRADAS) >= 120
    assert (
        GLOSARIO_REVISADO is False
    )  # cambia solo cuando un profesional lo revise (y se anota quién)
    assert glosario.estado()["revisado"] is False


def test_no_hay_nombres_ni_alias_repetidos():
    nombres = [n for n, _, _ in ENTRADAS]
    assert len(nombres) == len(set(nombres))
    alias = [normalizar(a) for _, lista, _ in ENTRADAS for a in lista]
    repetidos = {a for a in alias if alias.count(a) > 1}
    assert not repetidos, repetidos


def test_todas_las_entradas_estan_completas_y_bien_formadas():
    for nombre, alias, explicacion in ENTRADAS:
        assert nombre.strip() and alias, nombre
        assert 20 <= len(explicacion) <= 260, (nombre, len(explicacion))
        assert explicacion.endswith("."), nombre
        for a in alias:
            assert a == a.lower() and normalizar(a) == normalizar(a).strip(), (nombre, a)
            assert normalizar(a), (nombre, a)


@pytest.mark.parametrize("entrada", ENTRADAS, ids=[n for n, _, _ in ENTRADAS])
def test_ninguna_definicion_da_dosis_veredictos_ni_indicaciones(entrada):
    nombre, _alias, explicacion = entrada
    assert not PROHIBIDAS.search(explicacion), (nombre, explicacion)
    assert not garantias.posologia_sin_respaldo(explicacion, []), nombre
    # nada que diga si un resultado es bueno o malo para la persona
    assert not re.search(
        r"\b(grave|peligros\w*|preocupante|saludable|enfermo|enferma)\b", explicacion, re.I
    ), nombre


def test_las_definiciones_no_prometen_que_algo_indica_una_enfermedad():
    # «se usa para ver cómo funcionan los riñones» está bien; «indica enfermedad» no
    for nombre, _a, explicacion in ENTRADAS:
        assert (
            "indica enfermedad" not in explicacion.lower()
            and "significa que tiene" not in explicacion.lower()
        ), nombre


# ---------- búsqueda ----------
TEXTO = (
    "LABORATORIO. Hemoglobina 13,2 g/dL. Glucosa en ayunas 92 mg/dL. Colesterol LDL 160 mg/dL. "
    "Creatinina 0,8. Diagnóstico: hipertensión arterial. Control en un mes."
)


def test_encuentra_los_terminos_del_texto_en_orden_y_pone_al_final_los_de_estructura():
    nombres = [t["termino"] for t in glosario.terminos_en([TEXTO])]
    assert nombres[:5] == [
        "Hemoglobina",
        "Glucosa en ayunas",
        "Colesterol LDL",
        "Creatinina",
        "Hipertensión arterial",
    ]
    assert "Diagnóstico" in nombres and nombres.index("Diagnóstico") > nombres.index(
        "Hipertensión arterial"
    )


def test_un_alias_largo_tapa_al_corto_que_lo_contiene():
    nombres = [t["termino"] for t in glosario.terminos_en(["Glucosa en ayunas 92 mg/dL"])]
    assert nombres == ["Glucosa en ayunas"]  # no se repite «Glucosa»
    assert [t["termino"] for t in glosario.terminos_en(["Glucosa 92"])] == ["Glucosa"]


def test_no_confunde_palabras_que_solo_contienen_un_alias():
    # «tacto», «astucia» o «altura» no son TAC, AST ni ALT
    assert glosario.terminos_en(["El tacto y la astucia con la altura del paciente"]) == []


def test_funciona_sin_tildes_ni_mayusculas_y_con_guiones():
    nombres = [
        t["termino"]
        for t in glosario.terminos_en(
            ["HEMOGRAMA COMPLETO. Hemoglobina GLICOSILADA. CK-MB. CIE-10 I10"]
        )
    ]
    assert {"Hemograma", "Hemoglobina glicosilada (HbA1c)", "CK-MB", "CIE-10"} <= set(nombres)


def test_el_maximo_se_respeta_y_sin_coincidencias_no_hay_terminos():
    muchos = " ".join(a[0] for _, a, _ in ENTRADAS[:40])
    assert len(glosario.terminos_en([muchos])) == 8
    assert glosario.terminos_en(["Texto sin ningún término técnico conocido."]) == []


def test_los_terminos_comunes_existen_en_el_glosario():
    nombres = {n for n, _, _ in ENTRADAS}
    assert nombres >= COMUNES
