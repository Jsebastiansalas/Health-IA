"""Anonimización por patrones: qué enmascara, qué respeta y que siempre se puede restaurar."""

import uuid

import pytest

from app.privacidad.anonimizar import Anonimizador, enmascarar_texto, evidencias_para_la_nube
from app.rag.busqueda import FragmentoRecuperado

HISTORIA = (
    "Paciente: María Fernanda Gómez Rojas, CC 1.020.304.050. Fecha de nacimiento: 12/03/1985. "
    "Teléfono: 300 123 4567. Correo mariafg@correo.com. Reside en la Cra 15 # 93-60. "
    "Acudiente: Pedro Gómez. Médico: Dra. Laura Pérez. Diagnóstico: hipertensión arterial."
)


@pytest.mark.parametrize(
    "dato",
    [
        "María Fernanda Gómez Rojas",
        "1.020.304.050",
        "12/03/1985",
        "300 123 4567",
        "mariafg@correo.com",
        "Cra 15 # 93-60",
        "Pedro Gómez",
        "Laura Pérez",
    ],
)
def test_ningun_dato_personal_sobrevive_al_enmascarado(dato):
    assert dato not in Anonimizador().enmascarar(HISTORIA)


def test_conserva_lo_clinico_y_no_inventa_marcadores_donde_no_hay_datos():
    enmascarado = Anonimizador().enmascarar(HISTORIA)
    assert "hipertensión arterial" in enmascarado
    assert "Diagnóstico" in enmascarado
    assert enmascarar_texto("La garantía de cumplimiento será de doce (12) meses.") == (
        "La garantía de cumplimiento será de doce (12) meses."
    )


def test_los_numeros_de_una_licitacion_no_se_tapan():
    texto = (
        "CUM 19912345-1, registro sanitario INVIMA 2024M-0001234, NIT 900.123.456-7, "
        "cláusula 7.2 y presupuesto de $5.000.000.000. Adenda N° 2, pág. 14."
    )
    assert enmascarar_texto(texto) == texto


def test_el_mismo_dato_recibe_siempre_el_mismo_marcador():
    a = Anonimizador()
    texto = a.enmascarar("Paciente: Ana Ruiz. Más adelante: Paciente: Ana Ruiz, CC 52.111.222.")
    assert texto.count("[PERSONA_1]") == 2
    assert "[PERSONA_2]" not in texto
    assert "[DOCUMENTO_1]" in texto


def test_distintos_datos_reciben_marcadores_distintos():
    a = Anonimizador()
    texto = a.enmascarar("Paciente: Ana Ruiz. Acudiente: Luis Torres.")
    assert "[PERSONA_1]" in texto and "[PERSONA_2]" in texto


def test_ida_y_vuelta_recupera_el_texto_original():
    a = Anonimizador()
    assert a.restaurar(a.enmascarar(HISTORIA)) == HISTORIA


def test_restaura_marcadores_con_otra_capitalizacion_o_espacios():
    a = Anonimizador()
    a.enmascarar("Paciente: Ana Ruiz.")
    assert a.restaurar("Según [persona_1] y [ PERSONA 1 ] y [PERSONA-1].") == (
        "Según Ana Ruiz y Ana Ruiz y Ana Ruiz."
    )


def test_un_marcador_desconocido_se_deja_tal_cual():
    assert Anonimizador().restaurar("Dice [PERSONA_9].") == "Dice [PERSONA_9]."


def test_restaurar_json_recorre_cadenas_anidadas_sin_tocar_el_resto():
    a = Anonimizador()
    a.enmascarar("Paciente: Ana Ruiz.")
    datos = {
        "respuesta": "Es [PERSONA_1].",
        "citas": [{"extracto_literal": "Paciente: [PERSONA_1]"}],
        "n": 3,
    }
    assert a.restaurar_json(datos) == {
        "respuesta": "Es Ana Ruiz.",
        "citas": [{"extracto_literal": "Paciente: Ana Ruiz"}],
        "n": 3,
    }


def test_no_confunde_el_pronombre_ti_con_una_tarjeta_de_identidad():
    assert enmascarar_texto("Esto es para ti 12345678 veces.") == "Esto es para ti 12345678 veces."


def test_las_etiquetas_en_mayusculas_y_los_nombres_en_mayusculas_tambien_se_cubren():
    assert "JUAN PEREZ" not in enmascarar_texto("PACIENTE: JUAN PEREZ GOMEZ")


def _evidencia(texto: str) -> FragmentoRecuperado:
    return FragmentoRecuperado(
        id=uuid.uuid4(),
        documento_id=uuid.uuid4(),
        orden=1,
        pagina_inicio=1,
        pagina_fin=1,
        seccion="Datos del paciente: Ana Ruiz",
        contenido_texto=texto,
        metadata={},
        nombre_archivo="Historia_Ana_Ruiz.pdf",
        tipo_documento="HISTORIA_CLINICA",
        numero_adenda=0,
        sha256_original="0" * 64,
    )


def test_las_evidencias_para_la_nube_no_llevan_datos_ni_nombre_de_archivo_y_las_originales_no_cambian():
    a = Anonimizador()
    original = _evidencia("Paciente: Ana Ruiz, CC 52.111.222. Tensión 120/80.")
    original.vecinos = [_evidencia("Acudiente: Luis Torres.")]
    copias = evidencias_para_la_nube([original], a)
    nube = copias[0]
    assert "Ana Ruiz" not in nube.contenido_texto and "52.111.222" not in nube.contenido_texto
    assert "Ana Ruiz" not in nube.seccion and nube.nombre_archivo == "documento-1"
    assert "Luis Torres" not in nube.vecinos[0].contenido_texto
    assert "Tensión 120/80" in nube.contenido_texto
    # De las originales salen las citas verificadas: no se tocan.
    assert original.contenido_texto.startswith(
        "Paciente: Ana Ruiz"
    ) and original.nombre_archivo.endswith(".pdf")


@pytest.mark.parametrize(
    "texto",
    [
        "FORMULA MEDICA Paciente: Carlos Ruiz Mejia. CC 79.123.456.",
        "ORDEN MEDICA PACIENTE: CARLOS RUIZ MEJIA",
        "EPICRISIS MEDICO Nombre: Carlos Ruiz Mejia",
    ],
)
def test_un_titulo_con_una_etiqueta_no_se_come_la_etiqueta_real_del_nombre(texto):
    """«FORMULA MEDICA Paciente: …»: «MEDICA» no puede tomar «Paciente» como nombre y dejar el real al aire."""
    enmascarado = enmascarar_texto(texto)
    assert "carlos" not in enmascarado.lower() and "[PERSONA_1]" in enmascarado
