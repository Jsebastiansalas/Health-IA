"""Garantías deterministas: el corpus de límites clínicos y las comprobaciones sobre la salida del modelo."""

import uuid

import pytest

from app.rag import explicar, garantias, seguridad
from app.rag.busqueda import FragmentoRecuperado
from tests import corpus_limites as c


def test_el_corpus_es_suficientemente_grande():
    assert len(c.DOSIS) + len(c.RECETA) + len(c.DIAGNOSTICO) >= 55 and len(c.LEGITIMAS) >= 35


@pytest.mark.parametrize("pregunta", c.DOSIS)
def test_corpus_dosis(pregunta):
    limite = seguridad.detectar_limite_clinico(pregunta)
    assert limite is not None and limite.codigo == "dosis", pregunta


@pytest.mark.parametrize("pregunta", c.RECETA)
def test_corpus_receta(pregunta):
    limite = seguridad.detectar_limite_clinico(pregunta)
    assert limite is not None and limite.codigo == "receta", pregunta


@pytest.mark.parametrize("pregunta", c.DIAGNOSTICO)
def test_corpus_diagnostico(pregunta):
    limite = seguridad.detectar_limite_clinico(pregunta)
    assert limite is not None and limite.codigo == "diagnostico", pregunta


@pytest.mark.parametrize("pregunta", c.LEGITIMAS)
def test_corpus_legitimas_no_se_rechazan(pregunta):
    assert seguridad.detectar_limite_clinico(pregunta) is None, pregunta


# ---------- paráfrasis: cifras y juicios que el fragmento no trae ----------
FRAG = "Hemoglobina 13,2 g/dL (ref 12,0 - 15,5). Colesterol LDL 160 mg/dL (ref < 130) ALTO. Fecha: 12/11/2026."


@pytest.mark.parametrize(
    "afirmacion",
    [
        "La hemoglobina es 13,2 g/dL.",
        "La hemoglobina es 13.2 y el rango de referencia es de 12,0 a 15,5.",
        "El colesterol LDL es 160 mg/dL y está alto.",
        "Los análisis se hicieron el 12 de noviembre de 2026.",
        "El rango normal es entre 12,0 y 15,5.",
    ],
)
def test_una_parafrasis_respaldada_pasa(afirmacion):
    assert not garantias.afirma_sin_respaldo(afirmacion, FRAG)


@pytest.mark.parametrize(
    "afirmacion",
    [
        "La hemoglobina es 11,2 g/dL.",  # cifra cambiada
        "Los triglicéridos son 250 mg/dL.",  # cifra inventada
        "La hemoglobina está baja.",  # juicio contrario al documento
        "El valor de creatinina es grave.",  # juicio que el documento no hace
        "La hemoglobina es anormal.",
        "El resultado es muy preocupante.",
    ],
)
def test_una_parafrasis_con_cifra_o_juicio_ajeno_se_descarta(afirmacion):
    assert garantias.afirma_sin_respaldo(afirmacion, FRAG)


def _frag(texto):
    return FragmentoRecuperado(
        id=uuid.uuid4(),
        documento_id=uuid.uuid4(),
        orden=1,
        pagina_inicio=1,
        pagina_fin=1,
        seccion="",
        contenido_texto=texto,
        metadata={},
        nombre_archivo="d.pdf",
        tipo_documento="HISTORIA_CLINICA",
        numero_adenda=0,
        sha256_original="0" * 64,
    )


def test_la_explicacion_descarta_los_hallazgos_sin_respaldo_y_lo_avisa():
    datos = {
        "hay_evidencia": True,
        "de_que_trata": "Un laboratorio.",
        "hallazgos": [
            {
                "texto": "La hemoglobina es 13,2 g/dL.",
                "fragmento": "F1",
                "extracto_literal": "Hemoglobina 13,2 g/dL",
            },
            {
                "texto": "La hemoglobina es 9,0 g/dL.",
                "fragmento": "F1",
                "extracto_literal": "Hemoglobina 13,2 g/dL",
            },
            {
                "texto": "El colesterol está bajo.",
                "fragmento": "F1",
                "extracto_literal": "Colesterol LDL 160",
            },
        ],
        "terminos": [
            {"termino": "Paracetamol", "explicacion": "Se toman 500 mg cada 8 horas."},
            {"termino": "Hemoglobina", "explicacion": "Proteína que lleva oxígeno."},
        ],
        "senales_de_alarma": [],
        "preguntas_para_el_medico": [],
    }
    r = explicar.ensamblar_explicacion(datos, [_frag(FRAG)], 0.85)
    assert [h["texto"] for h in r.hallazgos] == ["La hemoglobina es 13,2 g/dL."]
    assert r.descartados == 2 and any("2 punto(s)" in a for a in r.alertas)
    # el glosario viene del texto del documento: el término inventado con dosis del modelo no aparece
    assert "Paracetamol" not in [t["termino"] for t in r.terminos]
    assert "Hemoglobina" in [t["termino"] for t in r.terminos]


# ---------- posología que ningún extracto respalda ----------
@pytest.mark.parametrize(
    "texto",
    [
        "Puedes tomar 500 mg cada 8 horas.",
        "Tome 2 tabletas al día.",
        "La dosis es de 1 g por día.",
        "Administre 10 ml cada 6 horas.",
        "Una tableta cada 12 horas.",
    ],
)
def test_una_posologia_sin_extracto_se_detecta(texto):
    assert garantias.posologia_sin_respaldo(texto, [])


def test_una_posologia_escrita_en_el_documento_citado_se_permite():
    extracto = "Acetaminofén 500 mg cada 8 horas por 5 días."
    assert not garantias.posologia_sin_respaldo("Tu orden indica 500 mg cada 8 horas.", [extracto])
    assert garantias.posologia_sin_respaldo("Tu orden indica 1000 mg cada 8 horas.", [extracto])


def test_el_texto_sin_posologia_no_se_toca():
    assert not garantias.posologia_sin_respaldo("El ibuprofeno puede irritar el estómago.", [])
    assert not garantias.posologia_sin_respaldo("Hemoglobina 13,2 g/dL, ref 12 - 15,5.", [])


def test_la_respuesta_con_dosis_inventada_se_sustituye_por_el_limite():
    cuerpo = {
        "respuestaAnalitica": "Tome 500 mg cada 8 horas.",
        "sinEvidencia": False,
        "citas": [{"extractoLiteral": "Ibuprofeno: puede irritar el estómago"}],
    }
    r = garantias.sin_posologia_inventada(cuerpo)
    assert (
        r["limiteClinico"] == {"codigo": "dosis", "origen": "salida"}
        and r["citas"] == []
        and r["sinEvidencia"]
    )
    assert "No puedo indicar dosis" in r["respuestaAnalitica"]


def test_la_respuesta_que_cita_la_dosis_del_documento_se_conserva():
    cuerpo = {
        "respuestaAnalitica": "Tu orden indica 500 mg cada 8 horas [1].",
        "sinEvidencia": False,
        "citas": [{"extractoLiteral": "Acetaminofén 500 mg cada 8 horas"}],
    }
    assert (
        garantias.sin_posologia_inventada(dict(cuerpo))["respuestaAnalitica"]
        == cuerpo["respuestaAnalitica"]
    )


def test_un_hallazgo_no_suena_a_orden_del_asistente():
    assert (
        garantias.atribuir_al_documento("Debe tomar una tableta cada 12 horas.")
        == "El documento indica que debe tomar una tableta cada 12 horas."
    )
    assert garantias.atribuir_al_documento("Tiene que volver en 8 días.").startswith(
        "El documento indica que tiene"
    )
    # lo que ya está en forma de dato no se toca
    assert (
        garantias.atribuir_al_documento("Losartán 50 mg cada 12 horas.")
        == "Losartán 50 mg cada 12 horas."
    )
    assert garantias.atribuir_al_documento("El control es en un mes.") == "El control es en un mes."
