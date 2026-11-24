# ruff: noqa: E501
"""Glosario curado de términos de exámenes y documentos médicos comunes.

Cada entrada explica QUÉ ES o QUÉ MIDE el término, en lenguaje sencillo y en general. Ninguna dice si el
valor de una persona es bueno o malo, ni qué enfermedad tiene, ni qué hacer, ni indica dosis.

ESTADO: escrito por el equipo de desarrollo; **pendiente de revisión por un profesional de la salud**
(química farmacéutica, medicina o enfermería). `GLOSARIO_REVISADO` pasa a True solo cuando alguien lo revise
y se anote quién y cuándo en `REVISION`.

Formato: (nombre que se muestra, [alias en minúsculas y SIN tildes que se buscan en el texto], explicación).
Los alias muy cortos o ambiguos se evitan a propósito (un alias que sea una palabra común daría falsos avisos).
"""

GLOSARIO_REVISADO = False

# Palabras de estructura que aparecen en casi cualquier documento: solo se muestran si sobra espacio, para
# no desplazar a los términos que sí ayudan a entender (hemoglobina, colesterol LDL, hipertensión…).
COMUNES = frozenset(
    {
        "Diagnóstico",
        "Hallazgos",
        "Antecedentes",
        "Control",
        "Lesión",
        "Valor de referencia",
        "Ayuno",
        "Fórmula médica",
        "Orden médica",
        "Cultivo",
        "Impresión diagnóstica",
        "Anamnesis",
        "Frecuencia cardíaca",
        "Tensión arterial",
    }
)
REVISION = "Pendiente de revisión profesional"

ENTRADAS: list[tuple[str, list[str], str]] = [
    # ---- Hemograma (cuadro hemático)
    (
        "Hemograma",
        ["hemograma", "cuadro hematico", "hemoleucograma"],
        "Examen de sangre que cuenta y describe los glóbulos rojos, los glóbulos blancos y las plaquetas.",
    ),
    (
        "Hemoglobina",
        ["hemoglobina"],
        "Proteína de los glóbulos rojos que transporta el oxígeno por el cuerpo. El examen mide cuánta hay en la sangre.",
    ),
    (
        "Hematocrito",
        ["hematocrito"],
        "Porcentaje de la sangre que está formado por glóbulos rojos.",
    ),
    (
        "Glóbulos rojos (eritrocitos)",
        ["globulos rojos", "eritrocitos", "hematies"],
        "Células de la sangre que llevan el oxígeno a los tejidos.",
    ),
    (
        "Leucocitos (glóbulos blancos)",
        ["leucocitos", "globulos blancos"],
        "Células de la sangre que forman parte de las defensas del cuerpo.",
    ),
    (
        "Plaquetas",
        ["plaquetas", "trombocitos"],
        "Fragmentos de células de la sangre que participan en la coagulación.",
    ),
    (
        "VCM (volumen corpuscular medio)",
        ["vcm", "volumen corpuscular medio"],
        "Tamaño promedio de los glóbulos rojos.",
    ),
    (
        "HCM (hemoglobina corpuscular media)",
        ["hcm", "hemoglobina corpuscular media"],
        "Cantidad promedio de hemoglobina que contiene cada glóbulo rojo.",
    ),
    (
        "Neutrófilos",
        ["neutrofilos"],
        "Tipo de glóbulo blanco; es el más abundante y participa en la defensa frente a bacterias.",
    ),
    (
        "Linfocitos",
        ["linfocitos"],
        "Tipo de glóbulo blanco que participa en las defensas, entre ellas la respuesta contra virus.",
    ),
    (
        "Eosinófilos",
        ["eosinofilos"],
        "Tipo de glóbulo blanco relacionado con las reacciones alérgicas y con algunos parásitos.",
    ),
    (
        "Monocitos",
        ["monocitos"],
        "Tipo de glóbulo blanco que ayuda a eliminar microorganismos y células dañadas.",
    ),
    (
        "VSG (velocidad de sedimentación globular)",
        ["vsg", "velocidad de sedimentacion"],
        "Examen que mide qué tan rápido se depositan los glóbulos rojos en un tubo de sangre; los médicos lo usan como un indicador general de inflamación.",
    ),
    # ---- Glucosa y metabolismo
    (
        "Glucosa en ayunas",
        [
            "glucosa en ayunas",
            "glicemia en ayunas",
            "glucemia en ayunas",
            "glicemia basal",
            "glucemia basal",
        ],
        "Cantidad de azúcar (glucosa) en la sangre después de varias horas sin comer.",
    ),
    (
        "Glucosa",
        ["glucosa", "glicemia", "glucemia"],
        "Azúcar que usa el cuerpo como principal fuente de energía. El examen mide cuánta hay en la sangre.",
    ),
    (
        "Hemoglobina glicosilada (HbA1c)",
        ["hemoglobina glicosilada", "hba1c", "hemoglobina glicada"],
        "Examen que refleja el promedio de la glucosa en la sangre durante los últimos dos a tres meses.",
    ),
    (
        "Curva de tolerancia a la glucosa",
        ["curva de tolerancia", "tolerancia a la glucosa", "prueba de sobrecarga"],
        "Prueba en la que se mide la glucosa antes y después de beber una cantidad definida de glucosa, para ver cómo la maneja el cuerpo.",
    ),
    (
        "Insulina",
        ["insulina"],
        "Hormona que produce el páncreas y que permite que la glucosa entre a las células.",
    ),
    # ---- Lípidos
    (
        "Colesterol total",
        ["colesterol total"],
        "Suma de los distintos tipos de colesterol de la sangre. El colesterol es una grasa que el cuerpo necesita para formar células y hormonas.",
    ),
    (
        "Colesterol LDL",
        ["colesterol ldl", "ldl"],
        "Tipo de colesterol que transporta la grasa hacia los tejidos. Los médicos lo vigilan porque se relaciona con el riesgo cardiovascular.",
    ),
    (
        "Colesterol HDL",
        ["colesterol hdl", "hdl"],
        "Tipo de colesterol que recoge el exceso de grasa de la sangre y lo lleva al hígado.",
    ),
    (
        "Colesterol VLDL",
        ["vldl"],
        "Tipo de colesterol que transporta principalmente triglicéridos en la sangre.",
    ),
    (
        "Triglicéridos",
        ["trigliceridos"],
        "Un tipo de grasa de la sangre que el cuerpo usa como reserva de energía.",
    ),
    (
        "Perfil lipídico",
        ["perfil lipidico", "lipidograma"],
        "Conjunto de exámenes que miden las grasas de la sangre: colesterol total, LDL, HDL y triglicéridos.",
    ),
    # ---- Riñón
    (
        "Creatinina",
        ["creatinina"],
        "Sustancia que producen los músculos y que los riñones eliminan. Su nivel en sangre se usa para ver cómo funcionan los riñones.",
    ),
    (
        "Nitrógeno ureico (BUN)",
        ["bun", "nitrogeno ureico"],
        "Mide la urea en la sangre, un desecho de la descomposición de las proteínas que eliminan los riñones.",
    ),
    (
        "Urea",
        ["urea"],
        "Desecho que se forma al descomponer las proteínas y que se elimina por la orina.",
    ),
    (
        "Ácido úrico",
        ["acido urico"],
        "Sustancia que se forma al descomponer unas sustancias llamadas purinas y que se elimina por los riñones.",
    ),
    (
        "Tasa de filtración glomerular (TFG)",
        ["filtracion glomerular", "tasa de filtrado", "tfg"],
        "Cálculo que estima cuánta sangre filtran los riñones por minuto.",
    ),
    # ---- Electrolitos
    (
        "Sodio",
        ["sodio"],
        "Mineral (electrolito) que ayuda a regular el agua del cuerpo y el funcionamiento de nervios y músculos.",
    ),
    (
        "Potasio",
        ["potasio"],
        "Mineral (electrolito) importante para el funcionamiento de los músculos, incluido el corazón, y de los nervios.",
    ),
    (
        "Cloro",
        ["cloro serico", "cloruro"],
        "Mineral (electrolito) que trabaja junto con el sodio y el potasio en el equilibrio de líquidos.",
    ),
    (
        "Calcio",
        ["calcio"],
        "Mineral necesario para los huesos, los músculos, los nervios y la coagulación.",
    ),
    (
        "Magnesio",
        ["magnesio"],
        "Mineral que participa en el funcionamiento de músculos, nervios y huesos.",
    ),
    (
        "Fósforo",
        ["fosforo"],
        "Mineral que trabaja junto con el calcio en la formación de los huesos.",
    ),
    # ---- Hígado
    (
        "ALT / TGP (alanina aminotransferasa)",
        ["alt", "tgp", "alanina aminotransferasa"],
        "Enzima que se encuentra sobre todo en el hígado. Su nivel en sangre se usa para ver cómo está el hígado.",
    ),
    (
        "AST / TGO (aspartato aminotransferasa)",
        ["ast", "tgo", "aspartato aminotransferasa"],
        "Enzima que se encuentra en el hígado, el corazón y los músculos.",
    ),
    (
        "Bilirrubina",
        ["bilirrubina"],
        "Pigmento amarillo que se forma al descomponer los glóbulos rojos y que el hígado elimina.",
    ),
    (
        "Fosfatasa alcalina",
        ["fosfatasa alcalina"],
        "Enzima presente en el hígado, los huesos y otros tejidos.",
    ),
    (
        "GGT (gamma glutamil transferasa)",
        ["ggt", "gamma glutamil transferasa"],
        "Enzima del hígado y de las vías biliares.",
    ),
    (
        "Albúmina",
        ["albumina"],
        "Proteína principal de la sangre; la produce el hígado y ayuda a mantener el líquido dentro de los vasos.",
    ),
    (
        "Proteínas totales",
        ["proteinas totales"],
        "Cantidad total de proteínas (albúmina y otras) que hay en la sangre.",
    ),
    (
        "Amilasa",
        ["amilasa"],
        "Enzima que producen el páncreas y las glándulas salivales para digerir los carbohidratos.",
    ),
    ("Lipasa", ["lipasa"], "Enzima que produce el páncreas para digerir las grasas."),
    # ---- Tiroides
    (
        "TSH (hormona estimulante de la tiroides)",
        ["tsh", "tirotropina", "hormona estimulante de la tiroides"],
        "Hormona de la hipófisis que le indica a la tiroides cuánta hormona producir.",
    ),
    (
        "T4 libre (tiroxina libre)",
        ["t4 libre", "tiroxina libre", "tiroxina"],
        "Una de las hormonas que produce la tiroides, que regula el ritmo del metabolismo.",
    ),
    (
        "T3 (triyodotironina)",
        ["t3 libre", "triyodotironina"],
        "Hormona activa de la tiroides, que regula el ritmo del metabolismo.",
    ),
    (
        "Tiroides",
        ["tiroides"],
        "Glándula del cuello que produce hormonas que regulan el metabolismo.",
    ),
    # ---- Inflamación, corazón, coagulación
    (
        "PCR (proteína C reactiva)",
        ["proteina c reactiva", "pcr ultrasensible", "pcr cuantitativa"],
        "Proteína que sube en la sangre cuando hay inflamación en el cuerpo.",
    ),
    (
        "Troponina",
        ["troponina"],
        "Proteína del músculo del corazón que pasa a la sangre cuando este se daña.",
    ),
    (
        "CK-MB",
        ["ck-mb", "ckmb", "creatina quinasa"],
        "Enzima presente en los músculos, entre ellos el corazón.",
    ),
    (
        "BNP / NT-proBNP",
        ["nt-probnp", "probnp", "peptido natriuretico"],
        "Sustancia que libera el corazón cuando está sometido a esfuerzo o sobrecarga.",
    ),
    (
        "INR",
        ["inr"],
        "Valor que indica cuánto tarda la sangre en coagular, estandarizado entre laboratorios.",
    ),
    (
        "Tiempo de protrombina (TP)",
        ["tiempo de protrombina"],
        "Examen que mide cuánto tarda la sangre en coagular por una de sus vías.",
    ),
    (
        "TTP / TTPa (tiempo parcial de tromboplastina)",
        ["tiempo parcial de tromboplastina", "ttpa"],
        "Examen que mide cuánto tarda la sangre en coagular por otra de sus vías.",
    ),
    ("Dímero D", ["dimero d"], "Sustancia que aparece cuando se deshace un coágulo de sangre."),
    # ---- Hierro y vitaminas
    (
        "Ferritina",
        ["ferritina"],
        "Proteína que almacena hierro en el cuerpo. Su nivel en sangre refleja las reservas de hierro.",
    ),
    ("Hierro sérico", ["hierro serico"], "Cantidad de hierro que circula en la sangre."),
    ("Transferrina", ["transferrina"], "Proteína que transporta el hierro por la sangre."),
    (
        "Vitamina B12",
        ["vitamina b12", "cobalamina"],
        "Vitamina necesaria para formar glóbulos rojos y para el sistema nervioso.",
    ),
    (
        "Ácido fólico (vitamina B9)",
        ["acido folico", "folato"],
        "Vitamina necesaria para formar células nuevas, entre ellas los glóbulos rojos.",
    ),
    (
        "Vitamina D",
        ["vitamina d", "25-hidroxivitamina", "25 oh"],
        "Vitamina que ayuda al cuerpo a absorber el calcio y cuida los huesos.",
    ),
    # ---- Orina y otros líquidos
    (
        "Uroanálisis (parcial de orina)",
        ["uroanalisis", "parcial de orina", "examen de orina", "citoquimico de orina"],
        "Examen de la orina que revisa su aspecto, su composición química y lo que se ve al microscopio.",
    ),
    (
        "Urocultivo",
        ["urocultivo"],
        "Examen que siembra la orina para ver si crecen bacterias y cuáles.",
    ),
    ("Proteinuria", ["proteinuria"], "Presencia de proteínas en la orina."),
    ("Hematuria", ["hematuria"], "Presencia de glóbulos rojos en la orina."),
    ("Leucocituria", ["leucocituria"], "Presencia de glóbulos blancos en la orina."),
    (
        "Nitritos (en orina)",
        ["nitritos"],
        "Dato del examen de orina que se relaciona con la presencia de ciertas bacterias.",
    ),
    (
        "Coprológico",
        ["coprologico", "coproscopico"],
        "Examen de la materia fecal para ver su aspecto y buscar parásitos u otros hallazgos.",
    ),
    (
        "Microalbuminuria",
        ["microalbuminuria"],
        "Presencia de cantidades muy pequeñas de albúmina en la orina.",
    ),
    # ---- Otros exámenes
    (
        "Antígeno prostático específico (PSA)",
        ["psa", "antigeno prostatico"],
        "Proteína que produce la próstata y que se mide en la sangre.",
    ),
    (
        "Citología cervicouterina",
        ["citologia", "papanicolau"],
        "Examen que toma células del cuello del útero para observarlas al microscopio.",
    ),
    (
        "Prueba de embarazo (β-hCG)",
        ["beta hcg", "gonadotropina corionica", "hcg"],
        "Mide la hormona que produce el cuerpo durante el embarazo.",
    ),
    (
        "Gasometría arterial",
        ["gasometria", "gases arteriales"],
        "Examen de sangre de una arteria que mide oxígeno, dióxido de carbono y el equilibrio ácido-base.",
    ),
    (
        "Hemocultivo",
        ["hemocultivo"],
        "Examen que siembra sangre para ver si crecen microorganismos.",
    ),
    (
        "Cultivo",
        ["cultivo"],
        "Examen que siembra una muestra para ver si crecen microorganismos y cuáles.",
    ),
    (
        "Antibiograma",
        ["antibiograma"],
        "Resultado que muestra a qué antibióticos responde una bacteria que creció en un cultivo.",
    ),
    ("Biopsia", ["biopsia"], "Toma de un pequeño trozo de tejido para estudiarlo al microscopio."),
    (
        "Patología",
        ["patologia", "anatomia patologica", "histopatologia"],
        "Estudio de tejidos o células al microscopio para describir lo que tienen.",
    ),
    # ---- Imágenes diagnósticas
    (
        "Radiografía",
        ["radiografia", "rayos x"],
        "Imagen del interior del cuerpo hecha con una pequeña dosis de radiación.",
    ),
    (
        "Ecografía (ultrasonido)",
        ["ecografia", "ultrasonido"],
        "Imagen del interior del cuerpo hecha con ondas de sonido, sin radiación.",
    ),
    (
        "Tomografía computarizada (TAC)",
        ["tomografia", "tac"],
        "Imágenes en cortes del cuerpo hechas con rayos X y un computador.",
    ),
    (
        "Resonancia magnética",
        ["resonancia magnetica", "resonancia"],
        "Imágenes detalladas del cuerpo hechas con un campo magnético, sin radiación.",
    ),
    ("Mamografía", ["mamografia"], "Radiografía de las mamas."),
    ("Densitometría ósea", ["densitometria"], "Examen que mide la densidad de los huesos."),
    (
        "Ecocardiograma",
        ["ecocardiograma"],
        "Ecografía del corazón que muestra su tamaño, sus válvulas y cómo se mueve.",
    ),
    (
        "Electrocardiograma (ECG)",
        ["electrocardiograma", "ekg"],
        "Registro de la actividad eléctrica del corazón.",
    ),
    ("Holter", ["holter"], "Registro del ritmo del corazón durante 24 horas o más."),
    (
        "Endoscopia digestiva",
        ["endoscopia", "esofagogastroduodenoscopia"],
        "Examen en el que se introduce un tubo con cámara para ver el esófago, el estómago y el duodeno.",
    ),
    (
        "Colonoscopia",
        ["colonoscopia"],
        "Examen en el que se introduce un tubo con cámara para ver el interior del intestino grueso.",
    ),
    (
        "Espirometría",
        ["espirometria"],
        "Examen que mide cuánto aire puedes sacar de los pulmones y con qué rapidez.",
    ),
    # ---- Términos de informes de imagen
    (
        "Infiltrado (pulmonar)",
        ["infiltrado", "infiltrados"],
        "Término de radiología para una zona del pulmón que se ve más opaca de lo habitual.",
    ),
    (
        "Consolidación",
        ["consolidacion"],
        "Término de radiología para una zona del pulmón que se ve rellena de material en lugar de aire.",
    ),
    (
        "Derrame pleural",
        ["derrame pleural"],
        "Presencia de líquido entre el pulmón y la pared del tórax.",
    ),
    (
        "Silueta cardíaca",
        ["silueta cardiaca", "silueta cardiomediastinica"],
        "Contorno del corazón y de las estructuras centrales del tórax, tal como se ve en una radiografía.",
    ),
    (
        "Campos pulmonares",
        ["campos pulmonares"],
        "Las zonas de los pulmones que se observan en una radiografía de tórax.",
    ),
    ("Nódulo", ["nodulo"], "Término para una pequeña masa redondeada en un órgano o tejido."),
    (
        "Quiste",
        ["quiste"],
        "Bolsa cerrada, generalmente llena de líquido, que se forma en un tejido.",
    ),
    (
        "Lesión",
        ["lesion"],
        "Término general para cualquier cambio o daño en un tejido o un órgano.",
    ),
    ("Hepatomegalia", ["hepatomegalia"], "Aumento del tamaño del hígado."),
    ("Esteatosis hepática", ["esteatosis"], "Presencia de grasa dentro del hígado."),
    (
        "Litiasis",
        ["litiasis", "calculos"],
        "Presencia de cálculos (piedras) en un órgano, por ejemplo la vesícula o el riñón.",
    ),
    (
        "Hernia",
        ["hernia"],
        "Salida de un órgano o tejido a través de una abertura de la pared que normalmente lo contiene.",
    ),
    # ---- Diagnósticos y condiciones frecuentes (definiciones generales)
    (
        "Hipertensión arterial",
        ["hipertension arterial", "hipertension", "hta"],
        "Condición en la que la presión de la sangre sobre las paredes de las arterias se mantiene por encima de los valores de referencia.",
    ),
    (
        "Diabetes mellitus",
        ["diabetes mellitus", "diabetes"],
        "Condición en la que el cuerpo tiene dificultad para manejar la glucosa de la sangre porque no produce suficiente insulina o no responde bien a ella.",
    ),
    (
        "Dislipidemia",
        ["dislipidemia", "hiperlipidemia", "hipercolesterolemia"],
        "Término para cuando las grasas de la sangre (colesterol o triglicéridos) están fuera de los valores de referencia.",
    ),
    (
        "Anemia",
        ["anemia"],
        "Condición en la que hay menos glóbulos rojos o hemoglobina de lo habitual, por lo que la sangre transporta menos oxígeno.",
    ),
    (
        "Hipotiroidismo",
        ["hipotiroidismo"],
        "Condición en la que la tiroides produce menos hormona de la necesaria.",
    ),
    (
        "Hipertiroidismo",
        ["hipertiroidismo"],
        "Condición en la que la tiroides produce más hormona de la necesaria.",
    ),
    (
        "Infección de vías urinarias",
        ["infeccion de vias urinarias", "infeccion urinaria", "ivu"],
        "Infección causada por microorganismos en alguna parte del sistema urinario, como la vejiga o los riñones.",
    ),
    ("Gastritis", ["gastritis"], "Inflamación del revestimiento del estómago."),
    (
        "Úlcera péptica",
        ["ulcera peptica", "ulcera gastrica", "ulcera duodenal"],
        "Herida abierta en el revestimiento del estómago o del duodeno.",
    ),
    (
        "Reflujo gastroesofágico",
        ["reflujo gastroesofagico", "erge"],
        "Regreso del contenido del estómago hacia el esófago.",
    ),
    (
        "Asma",
        ["asma"],
        "Condición de los pulmones en la que las vías respiratorias se inflaman y se estrechan, y causa dificultad para respirar.",
    ),
    (
        "EPOC",
        ["epoc", "enfermedad pulmonar obstructiva"],
        "Enfermedad pulmonar de larga duración que dificulta el paso del aire.",
    ),
    ("Neumonía", ["neumonia"], "Infección de los pulmones."),
    (
        "Obesidad",
        ["obesidad"],
        "Acumulación de grasa corporal por encima de los valores de referencia para la salud.",
    ),
    (
        "Sobrepeso",
        ["sobrepeso"],
        "Peso corporal por encima del que se considera de referencia para la estatura.",
    ),
    (
        "Osteoporosis",
        ["osteoporosis"],
        "Condición en la que los huesos pierden densidad y se vuelven más frágiles.",
    ),
    ("Artrosis", ["artrosis", "osteoartrosis"], "Desgaste del cartílago de las articulaciones."),
    (
        "Migraña",
        ["migrana"],
        "Tipo de dolor de cabeza recurrente, a menudo acompañado de otros síntomas.",
    ),
    ("Ansiedad", ["ansiedad"], "Estado de preocupación o inquietud intensa o frecuente."),
    (
        "Depresión",
        ["depresion"],
        "Condición del estado de ánimo con tristeza o pérdida de interés persistentes.",
    ),
    (
        "Insuficiencia renal",
        ["insuficiencia renal", "enfermedad renal cronica", "erc"],
        "Condición en la que los riñones filtran la sangre con menos eficacia de la habitual.",
    ),
    (
        "Insuficiencia cardíaca",
        ["insuficiencia cardiaca"],
        "Condición en la que el corazón bombea la sangre con menos eficacia de la necesaria.",
    ),
    ("Arritmia", ["arritmia"], "Alteración del ritmo de los latidos del corazón."),
    ("Dermatitis", ["dermatitis"], "Inflamación de la piel."),
    (
        "Rinitis alérgica",
        ["rinitis alergica", "rinitis"],
        "Inflamación de la nariz, a menudo por alergia, con congestión, estornudos o secreción.",
    ),
    ("Sinusitis", ["sinusitis"], "Inflamación de los senos paranasales."),
    ("Faringitis", ["faringitis"], "Inflamación de la garganta."),
    # ---- Palabras frecuentes en órdenes e informes
    (
        "Anamnesis",
        ["anamnesis"],
        "Parte de la historia clínica donde se anotan los datos que cuenta la persona: motivo de consulta, síntomas y antecedentes.",
    ),
    (
        "Antecedentes",
        ["antecedentes"],
        "Datos de la salud pasada de la persona y de su familia que se anotan en la historia clínica.",
    ),
    (
        "Impresión diagnóstica",
        ["impresion diagnostica"],
        "Lo que el profesional considera como posible diagnóstico al momento de la consulta; no siempre es definitivo.",
    ),
    (
        "Diagnóstico",
        ["diagnostico"],
        "Nombre que el profesional da a la condición que identifica en la persona.",
    ),
    ("Hallazgos", ["hallazgos"], "Lo que se observó o encontró durante un examen."),
    (
        "Interconsulta",
        ["interconsulta"],
        "Solicitud para que otro especialista valore a la persona.",
    ),
    (
        "Remisión",
        ["remision"],
        "Orden para que la persona sea atendida en otro nivel de atención o por otro servicio.",
    ),
    (
        "Control",
        ["control medico", "cita de control"],
        "Cita de seguimiento para revisar cómo evoluciona la persona.",
    ),
    (
        "Incapacidad",
        ["incapacidad"],
        "Documento que certifica un período en el que la persona no puede trabajar por motivos de salud.",
    ),
    (
        "Fórmula médica",
        ["formula medica"],
        "Documento donde el profesional escribe los medicamentos indicados a la persona.",
    ),
    (
        "Orden médica",
        ["orden medica"],
        "Documento donde el profesional solicita un examen, un procedimiento o una consulta.",
    ),
    (
        "Epicrisis",
        ["epicrisis"],
        "Resumen de la atención recibida durante una hospitalización, que se entrega al terminar.",
    ),
    (
        "Triage (triaje)",
        ["triage", "triaje"],
        "Clasificación que se hace en urgencias para decidir en qué orden se atiende a cada persona.",
    ),
    (
        "IMC (índice de masa corporal)",
        ["imc", "indice de masa corporal"],
        "Cálculo que relaciona el peso con la estatura.",
    ),
    (
        "Saturación de oxígeno",
        ["saturacion de oxigeno", "saturacion de o2", "sato2", "spo2"],
        "Porcentaje de la hemoglobina de la sangre que está cargada de oxígeno.",
    ),
    (
        "Tensión arterial",
        ["tension arterial", "presion arterial"],
        "Fuerza con la que la sangre empuja las paredes de las arterias; se anota con dos números.",
    ),
    (
        "Frecuencia cardíaca",
        ["frecuencia cardiaca", "pulso"],
        "Número de latidos del corazón por minuto.",
    ),
    ("Frecuencia respiratoria", ["frecuencia respiratoria"], "Número de respiraciones por minuto."),
    (
        "Ayuno",
        ["ayuno", "ayunas"],
        "Período sin comer ni beber (salvo agua) antes de algunos exámenes de sangre.",
    ),
    (
        "Valor de referencia",
        [
            "valor de referencia",
            "valores de referencia",
            "rango de referencia",
            "intervalo de referencia",
        ],
        "Intervalo de valores que el laboratorio usa como comparación; puede variar según el laboratorio, la edad y el sexo.",
    ),
    (
        "CIE-10",
        ["cie-10", "cie10"],
        "Clasificación internacional de enfermedades: códigos que se usan para nombrar cada diagnóstico en los documentos.",
    ),
]
