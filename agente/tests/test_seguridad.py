"""Señales de alarma en la pregunta: el aviso de urgencia va siempre primero y no depende del modelo."""

import pytest

from app.rag import seguridad


@pytest.mark.parametrize(
    ("pregunta", "codigo"),
    [
        ("Tengo dolor en el pecho desde hace una hora, ¿qué pastilla me tomo?", "pecho"),
        ("siento OPRESIÓN en mi pecho", "pecho"),
        ("No puedo respirar bien", "respiracion"),
        ("mi hijo tiene dificultad para respirar", "respiracion"),
        ("Tiene falta de aire desde ayer", "respiracion"),
        ("vomité con sangre", "sangrado"),
        ("sangrado abundante después del parto", "sangrado"),
        ("mi papá se desmayó y no despierta", "conciencia"),
        ("tuvo una convulsión", "conciencia"),
        ("tiene la cara torcida y dificultad para hablar", "neurologico"),
        ("creo que es una reacción alérgica grave, se me hincha la lengua", "alergia_grave"),
        ("se me cierra la garganta", "alergia_grave"),
        ("me tomé demasiadas pastillas", "intoxicacion"),
        ("¿qué hago si hay una sobredosis de acetaminofén?", "intoxicacion"),
        ("quiero morirme", "riesgo_vida"),
        ("quisiera quitarme la vida", "riesgo_vida"),
        ("tengo ganas de hacerme daño", "riesgo_vida"),
    ],
)
def test_detecta_las_senales_de_alarma(pregunta, codigo):
    urgencia = seguridad.detectar_urgencia(pregunta)
    assert urgencia is not None and urgencia.codigo == codigo
    assert "123" in urgencia.mensaje


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuál es el plazo de entrega según la adenda 2?",
        "¿Qué significa hemoglobina en mi examen?",
        "¿Para qué sirve el losartán?",
        "¿Qué garantías exige el pliego?",
        "Me dolió la cabeza ayer, ¿qué es una cefalea tensional?",
        "¿Está vigente el registro sanitario de la metformina?",
    ],
)
def test_no_alarma_con_preguntas_normales(pregunta):
    assert seguridad.detectar_urgencia(pregunta) is None


def test_el_riesgo_para_la_vida_tiene_prioridad_y_otro_mensaje():
    u = seguridad.detectar_urgencia("tengo dolor de pecho y quiero morirme")
    assert u is not None and u.codigo == "riesgo_vida"
    assert "No tienes que enfrentarlo solo" in u.mensaje
    general = seguridad.detectar_urgencia("tengo dolor en el pecho")
    assert general is not None and general.mensaje != u.mensaje


def test_ignora_acentos_mayusculas_y_espacios_de_mas():
    assert seguridad.detectar_urgencia("  DOLOR   EN   EL   PECHO  ") is not None
    assert seguridad.detectar_urgencia("Dolor en el pécho") is not None


def test_con_urgencia_pone_el_aviso_primero_y_conserva_las_alertas():
    cuerpo = {"respuestaAnalitica": "x", "alertas": ["Otra alerta"], "sinEvidencia": False}
    r = seguridad.con_urgencia(cuerpo, "tengo dolor en el pecho")
    assert r["urgencia"]["codigo"] == "pecho"
    assert r["alertas"][0] == r["urgencia"]["mensaje"] and r["alertas"][1] == "Otra alerta"
    assert r["respuestaAnalitica"] == "x"  # no toca la respuesta


def test_con_urgencia_sin_alarma_deja_la_respuesta_intacta():
    cuerpo = {"alertas": ["a"]}
    r = seguridad.con_urgencia(cuerpo, "¿Qué garantías exige el pliego?")
    assert r["urgencia"] is None and r["alertas"] == ["a"]


def test_con_urgencia_funciona_aunque_no_haya_lista_de_alertas():
    r = seguridad.con_urgencia({}, "no puedo respirar")
    assert r["alertas"] == [r["urgencia"]["mensaje"]]
