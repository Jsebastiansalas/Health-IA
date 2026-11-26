# ruff: noqa: E501
"""Corpus para medir la anonimización. Todo es inventado; ningún nombre corresponde a un paciente.

Los nombres de persona van entre ⟦ ⟧. Lo demás NO debe taparse: epónimos, medicamentos, instituciones y
lugares que parecen nombres.

Dos partes con papeles distintos:
- DESARROLLO: contra él se puede ajustar el código.
- RESERVA: se escribió antes que la segunda capa y NO se usa para ajustarla (no se agregan a las listas
  nombres solo porque aparezcan aquí). Es la cifra que más se parece a lo que pasará con documentos nuevos.

Límite: lo escribió la misma persona que escribió el código y es pequeño. No sustituye una medición con
documentos reales anonimizados.
"""

DESARROLLO_NOMBRES = [
    "Fue atendido en urgencias por ⟦Juan Pérez⟧ a las tres de la tarde.",
    "La señora acude acompañada de su hija ⟦María Fernanda Rojas⟧.",
    "⟦Carlos Andrés Gómez⟧ refiere dolor abdominal desde hace tres días.",
    "Se explica a ⟦Luz Marina Cárdenas⟧ el plan de manejo y refiere entender.",
    "Firma: ⟦Andrea Castaño Ruiz⟧ - Bacterióloga",
    "Informe validado por ⟦HERNÁN DARÍO OSPINA⟧ el mismo día.",
    "Vive con su esposo ⟦Jorge⟧ y dos hijos.",
    "Acude con su mamá, ⟦Gloria⟧, quien relata el cuadro.",
    "Su hijo ⟦Santiago⟧ la trae a consulta.",
    "Se comunica resultado a ⟦Diana Patricia Moreno Salazar⟧ por vía telefónica.",
    "Revisado por: ⟦Felipe Restrepo⟧",
    "Muestra tomada por ⟦Yolanda Beltrán⟧ en ayunas.",
    "Control programado con ⟦Ricardo Villamizar⟧ de medicina interna.",
    "Paciente: ⟦Ana Lucía Torres⟧. En la tarde ⟦Ana Lucía⟧ refiere mejoría.",
    "Paciente: ⟦Carlos Ruiz Mejía⟧\nSe cita al señor ⟦Ruiz Mejía⟧ en un mes.",
    "Paciente: ⟦Rosa Elvira Niño⟧. ⟦Rosa⟧ niega alergias.",
    "Nombre: ⟦PEDRO PABLO SUAREZ⟧\nObservaciones: ⟦Pedro⟧ asiste solo.",
    "Entrevista a ⟦Nubia Esperanza Prieto⟧, cuidadora principal.",
    "La enfermera ⟦Paola Andrea⟧ registra los signos vitales.",
    "Autoriza el procedimiento ⟦Guillermo León Zapata⟧.",
    "En compañía de ⟦José Manuel Cifuentes⟧, su acudiente.",
    "Se deja nota: ⟦Martha Cecilia Duarte⟧ solicita copia de la historia.",
]

DESARROLLO_SIN_NOMBRES = [
    "Paciente con enfermedad de Parkinson en tratamiento.",
    "Antecedente de síndrome de Down en la familia.",
    "Signo de Murphy positivo en el examen físico.",
    "Escala de Glasgow 15 sobre 15.",
    "Remitido al Hospital San José de Bogotá.",
    "Atendido en la Clínica Santa María del Lago.",
    "Control en el Hospital Pablo Tobón Uribe.",
    "Vive en Santa Marta y viaja con frecuencia a San Andrés.",
    "Se formula Losartán 50 mg y Metformina 850 mg.",
    "Hemoglobina Glicosilada 7,1 por ciento.",
    "RESULTADOS DE LABORATORIO CLINICO",
    "Antecedente de Diabetes Mellitus Tipo Dos y Hipertensión Arterial.",
    "Afiliado a Nueva EPS, régimen contributivo.",
    "Prueba de Papanicolaou sin alteraciones.",
    "Coloración de Gram negativa en la muestra.",
    "Anticuerpos contra el virus de Epstein Barr positivos.",
    "Tiroiditis de Hashimoto diagnosticada hace dos años.",
    "Fractura de Colles en el antebrazo izquierdo.",
    "Valorado por Medicina Interna y Cirugía General.",
    "Se solicita ecografía Doppler de miembros inferiores.",
    "Cultivo positivo para Escherichia Coli.",
    "Se sospecha esófago de Barrett según la endoscopia.",
    "Dolor en fosa iliaca derecha con McBurney positivo.",
    "Cita en Marzo para control de presión arterial.",
    "La Cruz Roja Colombiana atendió el traslado.",
    "Manejo con Acetaminofén si presenta dolor, según fórmula.",
    "Examen realizado en el laboratorio San Rafael.",
    "Paciente en buen estado general, alerta y orientado.",
    "Planifica con Yasmin desde hace un año; antes usaba Diane.",
    "Antecedente de uso de Mirena como método anticonceptivo.",
    "RECOMENDACIONES GENERALES AL EGRESO",
    "Consulta De Control Por Medicina Familiar",
    "Departamento del Valle del Cauca, municipio de La Unión.",
    "Dieta baja en sal y Rosa Mosqueta tópica en la cicatriz.",
]

RESERVA_NOMBRES = [
    "Se recibe a ⟦Yurany Mosquera⟧ remitida desde urgencias.",
    "El joven ⟦Brayan Stiven Quiñones⟧ consulta por cefalea.",
    "Vive con su abuela ⟦Nilsa Cuesta⟧.",
    "Resultado entregado a ⟦Wilmar Arboleda Hinestroza⟧.",
    "Acompaña la señora ⟦Tránsito Chindoy⟧, su cuñada.",
    "Procedimiento explicado a ⟦Leidy Johanna Bermúdez⟧.",
    "Validado electrónicamente por ⟦OSCAR IVAN QUINTERO⟧.",
    "Su pareja ⟦Camilo⟧ firma el consentimiento.",
    "Interconsulta solicitada por ⟦Adriana Valencia⟧.",
    "Paciente: ⟦Edinson Palacios Rentería⟧. ⟦Edinson⟧ niega fumar.",
    "Nombre: ⟦Sandra Milena Ortiz⟧\nSe orienta a ⟦Sandra Milena⟧ sobre signos de alarma.",
    "Relata ⟦Ezequiel Barragán⟧ que el dolor inició en la noche.",
    "La cuidadora ⟦Concepción⟧ administra los medicamentos.",
    "Transcribe: ⟦Julián Esteban Marín⟧",
    "Se entrega incapacidad a ⟦Fabiola Urrutia de Caicedo⟧.",
    "Su hermano ⟦Álvaro⟧ lo acompaña.",
]

RESERVA_SIN_NOMBRES = [
    "Enfermedad de Chagas descartada por serología.",
    "Maniobra de Valsalva sin hallazgos.",
    "Remitido a la Fundación Santa Fe de Bogotá.",
    "Paciente natural de Buenaventura, procedente de Cali.",
    "Se indica control con Optometría y Salud Ocupacional.",
    "Colesterol de Baja Densidad elevado según el informe.",
    "Prueba de Coombs directa negativa.",
    "Linfoma de Hodgkin en remisión.",
    "Trasladado en ambulancia al Hospital Universitario del Valle.",
    "Se formula Enalapril 20 mg y Atorvastatina 40 mg.",
    "Parcial de Orina sin nitritos.",
    "Afiliado a Sanitas desde hace cinco años.",
    "Escala de Apgar normal al nacer.",
    "Vive en el barrio Simón Bolívar.",
    "Presenta Dolor Lumbar Crónico sin irradiación.",
    "Manguito rotador íntegro en la resonancia magnética.",
]
