"""Segunda capa de anonimización: nombres de persona sin etiqueta, medida contra el corpus."""

import pytest

from app.core.config import get_settings
from app.privacidad.anonimizar import Anonimizador, enmascarar_texto, evidencias_para_la_nube
from evaluacion import corpus_nombres as corpus
from evaluacion.anonimizacion import informe, medir
from tests.test_cronologia import _frag


def test_en_desarrollo_se_ocultan_casi_todos_los_nombres_sin_tapar_lo_demas():
    m = medir(corpus.DESARROLLO_NOMBRES + corpus.DESARROLLO_SIN_NOMBRES, enmascarar_texto)
    assert m.cobertura >= 0.95, (informe("desarrollo", m), m.escapados)
    assert m.tapado_de_mas <= 0.005, (informe("desarrollo", m), m.de_mas)


def test_los_epinimos_medicamentos_instituciones_y_lugares_quedan_intactos():
    for texto in corpus.DESARROLLO_SIN_NOMBRES:
        assert enmascarar_texto(texto) == texto


def test_lo_que_vuelve_del_modelo_es_exactamente_lo_escrito():
    anon = Anonimizador()
    original = "Fue atendido por Juan Pérez. Después JUAN PÉREZ GÓMEZ firmó; Juan está estable."
    enviado = anon.enmascarar(original)
    assert "Juan" not in enviado and "JUAN" not in enviado
    assert anon.restaurar(enviado) == original


def test_un_nombre_con_etiqueta_no_se_lleva_la_linea_siguiente():
    anon = Anonimizador()
    enviado = anon.enmascarar("Paciente: Carlos Ruiz Mejía\nSe cita en un mes.")
    assert enviado == "Paciente: [PERSONA_1]\nSe cita en un mes."
    assert anon.restaurar("[PERSONA_1]") == "Carlos Ruiz Mejía"


def test_un_nombre_conocido_se_oculta_en_todos_los_fragmentos_aunque_la_etiqueta_venga_despues():
    a = _frag("Yurleidis refiere dolor. Se cita a Chindoy Jacanamijoy.")
    b = _frag("Paciente: Yurleidis Chindoy Jacanamijoy")
    anon = Anonimizador()
    copias = evidencias_para_la_nube([a, b], anon)
    todo = " ".join(c.contenido_texto for c in copias)
    assert "Yurleidis" not in todo and "Chindoy" not in todo and "Jacanamijoy" not in todo
    assert "refiere dolor" in todo
    assert anon.restaurar(copias[0].contenido_texto) == a.contenido_texto


def test_lo_aprendido_no_tapa_la_misma_palabra_en_minuscula():
    anon = Anonimizador()
    enviado = anon.enmascarar("Paciente: Rosa Flores\nPresenta mancha rosa y flores secas en casa.")
    assert enviado.endswith("Presenta mancha rosa y flores secas en casa.")


def test_la_segunda_capa_se_puede_apagar(monkeypatch):
    monkeypatch.setattr(get_settings(), "anonimizar_nombres_sueltos", False)
    texto = "Fue atendido por Juan Pérez."
    assert enmascarar_texto(texto) == texto
    assert "[PERSONA_1]" in enmascarar_texto("Paciente: Juan Pérez")


def test_en_la_reserva_no_se_retrocede():
    """Cifra medida al escribir la segunda capa (12 de 18). No se ajustan las listas contra la reserva:
    este piso solo avisa si un cambio la empeora."""
    m = medir(corpus.RESERVA_NOMBRES + corpus.RESERVA_SIN_NOMBRES, enmascarar_texto)
    assert m.cobertura >= 0.66, (informe("reserva", m), m.escapados)
    assert m.tapado_de_mas <= 0.005, (informe("reserva", m), m.de_mas)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        (
            "EPICRISIS Paciente: Lucia Ramirez Ortiz Fecha de ingreso: 02/06/2025",
            "EPICRISIS Paciente: [PERSONA_1] Fecha de ingreso: 02/06/2025",
        ),
        ("Paciente: Ana Torres Edad: 40 años", "Paciente: [PERSONA_1] Edad: 40 años"),
        ("Paciente: Juan de la Cruz Sexo: M", "Paciente: [PERSONA_1] Sexo: M"),
        ("Paciente: Rosa Salud Medina Diagnóstico: sano", "Paciente: [PERSONA_1] Diagnóstico: sano"),
    ],
)
def test_en_un_solo_renglon_el_nombre_no_se_lleva_el_campo_siguiente(texto, esperado):
    assert enmascarar_texto(texto) == esperado
