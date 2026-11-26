# ruff: noqa: E501
"""Segunda capa de anonimización: nombres de persona escritos SIN etiqueta.

No es un modelo de reconocimiento de entidades: son reglas sobre secuencias de palabras con mayúscula.
Se oculta una secuencia cuando
- trae un nombre de pila conocido («Juan Pérez», o «Santiago» solo si no es además una palabra corriente);
- son dos o más apellidos conocidos («Ruiz Mejía»);
- la anuncia un parentesco, un trato o una firma («su abuela X», «Revisado por: X»), esté o no en las listas;
- repite palabras de un nombre ya detectado en la misma consulta («Paciente: X … X refiere dolor»).

No se toca lo que es una institución, un lugar o un epónimo («Hospital Pablo Tobón Uribe», «Santa Marta»,
«enfermedad de Parkinson»). Las listas no incluyen nombres que son marcas de medicamentos (Yasmin, Diane).

Límite: un nombre poco común, sin etiqueta, sin parentesco ni firma, SE ESCAPA. La cifra medida está en
`evaluacion/corpus_nombres.py`.
"""

import re
import unicodedata


def _norm(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sin.lower()


def _lista(texto: str) -> frozenset[str]:
    return frozenset(texto.split())


# Nombres de pila frecuentes en Colombia (sin tildes).
NOMBRES_DE_PILA = _lista("""
adela adolfo adrian adriana agustin aida alba albeiro alberto alcira alejandra alejandro alexander alexandra
alfonso alfredo alicia alirio alonso alvaro amalia amanda amelia amparo ana anabel anderson andrea andres angela
angelica angie anibal antonio arturo astrid augusto aura aurora beatriz belen benjamin bernardo bertha blanca
brenda camila camilo carlos carmen carolina catalina cecilia cesar clara claudia consuelo constanza cristian
cristina daniel daniela dario david deisy diana diego dora doris edgar edilberto edison eduardo edwin elena
eliana elias elizabeth elkin elsa elvira emilia emilio enrique erika ernesto esperanza esteban estefania
esther eugenia eva fabian fabio felipe felix fernanda fernando flor flora francisco freddy gabriel gabriela
german gilberto gildardo giovanni gladys gloria gonzalo graciela gregorio guillermo gustavo harold hector
helena henry hernan hernando hilda horacio hugo humberto ignacio ines ingrid irene isabel isabella ivan jaime
jairo janeth javier jazmin jeferson jennifer jenny jeronimo jessica jesus jhon jimena joaquin johan johana john
jonathan jorge jose josefina juan juana julian juliana julio karen karina katherine kelly laura leandro leonardo
leonor lida ligia liliana lina lorena lourdes lucia luciana luis luisa luz magda magdalena manuel manuela marcela
marco marcos margarita maria mariana maribel mariela marina mario marisol marleny marta martha martin mateo matias
mauricio maximiliano mercedes miguel milena miriam monica myriam nancy natalia nataly nelson nestor nicolas
nidia nohora nora norberto norma nubia ofelia olga omar orlando oscar pablo paola patricia paula pedro pilar
rafael ramiro ramon raul rebeca reinaldo ricardo rigoberto roberto rocio rodolfo rodrigo roger rolando rosa
rosalba rosario ruben ruby ruth salomon salome samuel sandra santiago sara saul sebastian sergio silvia simon
sofia soledad sonia stella susana tatiana teodoro teresa tomas valentina valeria vanessa veronica vicente victor
victoria viviana walter william wilson ximena yamile yaneth yenny yesenia yolanda zoraida
""")
# También son palabras corrientes: solos no bastan; hacen falta apellido o una señal.
AMBIGUOS = _lista("""
alba amparo angel aurora blanca clara consuelo constanza esperanza flor gloria luz marina mercedes milena pilar
rosa rosario soledad victoria stella dora marco julio
""")

APELLIDOS = _lista("""
acevedo acosta agudelo aguilar aguirre alarcon alvarado alvarez amaya andrade angulo arango araujo arbelaez
arboleda ardila arenas arevalo arias ariza arrieta arroyave arroyo avendano avila ayala ballesteros barbosa
barragan barrera barreto barrios bautista becerra bedoya bejarano beltran benavides benitez bermudez bernal
betancourt betancur blanco bohorquez bolivar bonilla borja botero bravo briceno buitrago burbano bustamante
bustos caballero cabrera cadavid caicedo calderon calle camacho camargo campos canon cano cantillo carballo
cardenas cardona carmona caro carrascal carreno carrillo carvajal casallas casas castaneda castano castellanos
castiblanco castillo castro cepeda cespedes chacon chaparro chavez cifuentes clavijo cobo coronado correa cortes
cuellar cuervo cuesta daza delgado diaz duarte duque duran echeverri echeverry enriquez escobar espinosa
espinel estrada fajardo fernandez figueroa florez forero franco fuentes galeano galindo gallego gallo galvis
gamboa gaona garcia garzon gaviria gil giraldo gomez gonzalez gordillo granados grajales grisales guarin guerrero
guevara guillen guio gutierrez guzman henao heredia hernandez herrera hidalgo higuera hincapie holguin hoyos
hurtado ibanez ibarra infante izquierdo jaimes jaramillo jimenez joya lancheros lara latorre leal ledesma
leguizamon leiva lemus leon lizarazo llanos loaiza lombana londono lopez lozano lucumi luna macias maldonado
mancera manrique mantilla manzano marin marquez marroquin martinez mateus mayorga medina mejia melendez melo
mendez mendoza mendieta meneses mesa meza millan miranda molano molina moncada monroy monsalve montanez montes
montoya mora morales moreno mosquera motta moya munoz murcia murillo narvaez navarrete navarro neira nieto
nino noguera novoa nunez obando ocampo ochoa ojeda olarte olaya oliveros ordonez orjuela orozco orrego ortega
ortiz osorio ospina otalora pabon pacheco padilla paez palacio palacios palomino parada pardo paredes parra
patino pena penagos penaloza peralta perdomo perea perez perilla pineda pinilla pinto pinzon piraquive plazas
polania polo porras portilla posada prada prieto puentes pulido quevedo quiceno quintana quintero quiroga
quiroz ramirez ramos rangel rendon rengifo restrepo reyes riano ricaurte rico rincon rios rivas rivera
rivero roa robayo robles rocha rodriguez rojas roldan rolon romero roncancio rosales rosas rozo rubiano rubio
rueda ruiz saavedra saenz saiz salamanca salas salazar salcedo saldarriaga salgado salinas samaca samper
sanabria sanchez sandoval santacruz santamaria santana santos sarmiento segura sepulveda serna serrano sierra
silva sogamoso solano soler solorzano sosa soto suarez tabares tafur tamayo tapias tarazona tejada tellez
tello tinjaca tobon tocora toro torres tovar triana trujillo turriago ulloa urbina urrea useche vaca valbuena
valderrama valdes valencia valenzuela valero vallejo vanegas varela vargas vasquez vega velandia velasco
velasquez velez vera vergara viafara vidal villa villalba villalobos villamil villamizar villanueva villareal
villarreal villegas viloria yepes zambrano zamora zapata zarate zuluaga zuniga
""")

# Palabras con mayúscula que nunca son parte de un nombre: cortan la secuencia.
NO_SON_NOMBRE = _lista("""
a acude acompana actualmente ademas al alerta alta ambos analisis antecedente antecedentes antes aqui asi atendido
autoriza ayer bacteriologa bacteriologo baja buen buena cedula cita clinica clinico como con consulta control
cuando cuidador cuidadora de del departamento despues dia diagnostico dieta doctor doctora documento dolor don
dona dr dra durante edad egreso el ella en enfermedad enfermera enfermero entrevista eps es esta este examen
fecha femenino firma fue general hace hallazgos hasta hijo hija historia hoja hoy informe ingreso interconsulta
la laboratorio las le lo los luego manana manejo masculino medicina medico medica mg ml municipio muestra no
nombre nota observaciones orientado paciente para pendiente por presenta presion procedimiento programada
programado que recibe recomendaciones refiere registra relata remitido remitida resultado resultados revisado se
senor senora servicio sexo si sin sr sra su sus tambien telefono tipo toma tomada tomado tras tratamiento un una
unidad urgencias valorado validado vive y ya enero febrero marzo abril mayo junio julio agosto septiembre
octubre noviembre diciembre lunes martes miercoles jueves viernes sabado domingo
hospital fundacion instituto centro universitario barrio vereda cruz roja nueva salud mosqueta
""") - NOMBRES_DE_PILA

_MINUSCULA = r"a-záéíóúñü"
_TOKEN = re.compile(
    r"(?P<marcador>\[[A-Z]+_\d+\])|(?<![\w])(?P<palabra>[A-ZÁÉÍÓÚÑÜ](?:[" + _MINUSCULA + r"]+|[A-ZÁÉÍÓÚÑÜ]+))(?![\w])"
)
_ENLACE = re.compile(r"[ \t]+(?:(?:de|del|DE|DEL)[ \t]+(?:(?:la|los|las|LA|LOS|LAS)[ \t]+)?)?")
# Lo que precede (en el mismo renglón) a una institución, un lugar o un epónimo.
_NO_ES_PERSONA = re.compile(
    r"\b(?:hospital|clinica|fundacion|laboratorio|instituto|centro|colegio|barrio|vereda|municipio|"
    r"avenida|parque|enfermedad|sindrome|signo|escala|prueba|maniobra|linfoma|tiroiditis|fractura|"
    r"coloracion|virus|esofago|angina|reflejo|test|tecnica|metodo|tumor|ley)"
    r"(?:[ \t]+(?:universitari[oa]|regional|de|del|la|los|las))*[ \t]+$"
)
# Parentescos, tratos y firmas: lo que sigue es una persona aunque no esté en las listas.
_ANUNCIA_PERSONA = re.compile(
    r"(?:\b(?:hij[oa]|espos[oa]|pareja|mama|papa|madre|padre|abuel[oa]|herman[oa]|cunad[oa]|niet[oa]|"
    r"sobrin[oa]|suegr[oa]|prim[oa]|cuidador[a]?|acudiente|acompanante|senor[a]?|sr\.|sra\.|don|dona|"
    r"firma|se llama)|"
    r"\b(?:atendid[oa]|revisad[oa]|validad[oa](?: electronicamente)?|tomada|elaborad[oa]|transcrit[oa]) por|"
    r"\btranscribe)"
    r"[ \t]*[,:.]?[ \t]+$"
)
# Palabras que encabezan un campo de un documento. A propósito sin las que también son apellidos (Cruz).
_ENCABEZAN_CAMPO = _lista("""
alergias antecedentes cama cedula cita ciudad control diagnostico direccion documento edad egreso eps estado
examen fecha firma genero hallazgos historia hora identificacion informe ingreso medicamentos medico motivo
muestra nacimiento nombre observaciones paciente procedimiento recomendaciones remitido resultado resultados
servicio sexo telefono tipo toma tratamiento
""")

_PRIMERA_SANTA = {"san", "santa", "santo"}
_SALTO = re.compile(r"\s*\n\s*")
# Tras la primera palabra de un renglón: dos puntos (un campo) o una palabra en minúscula (una frase).
_ABRE_OTRA_COSA = re.compile(r"[^\S\n]*(?::|[" + _MINUSCULA + r"]{2,})")


def secuencias(texto: str) -> list[list[re.Match[str]]]:
    """Grupos de palabras con mayúscula seguidas en un mismo renglón (admite «de», «del», «de la»)."""
    grupos: list[list[re.Match[str]]] = []
    actual: list[re.Match[str]] = []
    for m in _TOKEN.finditer(texto):
        if m["marcador"] or _norm(m["palabra"]) in NO_SON_NOMBRE:
            if actual:
                grupos.append(actual)
            actual = []
            continue
        if actual and not _ENLACE.fullmatch(texto, actual[-1].end(), m.start()):
            grupos.append(actual)
            actual = []
        actual.append(m)
    if actual:
        grupos.append(actual)
    return grupos


def _contexto(texto: str, inicio: int) -> str:
    """Lo que hay antes en el mismo renglón, y las palabras cortadas («Revisado por:»)."""
    renglon = texto.rfind("\n", 0, inicio) + 1
    return _norm(texto[max(renglon, inicio - 60) : inicio])


def detectar(texto: str, conocidos: set[str]) -> list[tuple[int, int]]:
    """Tramos (inicio, fin) que son nombres de persona."""
    tramos: list[tuple[int, int]] = []
    for grupo in secuencias(texto):
        palabras = [_norm(m["palabra"]) for m in grupo]
        antes = _contexto(texto, grupo[0].start())
        if palabras[0] in _PRIMERA_SANTA or _NO_ES_PERSONA.search(antes):
            continue
        if _ANUNCIA_PERSONA.search(antes):
            tramos.append((grupo[0].start(), grupo[-1].end()))
            continue
        pila = next((i for i, p in enumerate(palabras) if p in NOMBRES_DE_PILA), None)
        if pila is not None and len(palabras) - pila >= 2:
            tramos.append((grupo[pila].start(), grupo[-1].end()))
        elif len(palabras) >= 2 and all(p in APELLIDOS for p in palabras):
            tramos.append((grupo[0].start(), grupo[-1].end()))
        elif pila is not None and palabras[pila] not in AMBIGUOS:
            tramos.append(grupo[pila].span("palabra"))
        else:
            # Lo ya identificado en la consulta, aunque venga solo o junto a otras palabras.
            inicio = fin = None
            for m, p in zip(grupo, palabras, strict=True):
                if p in conocidos:
                    inicio = m.start() if inicio is None else inicio
                    fin = m.end()
                elif inicio is not None:
                    tramos.append((inicio, fin))
                    inicio = None
            if inicio is not None:
                tramos.append((inicio, fin))
    return tramos


def sin_lo_que_sigue(texto: str, inicio: int, fin: int) -> str:
    """El nombre que sigue a una etiqueta, sin lo que ya es otro campo o frase.

    En un mismo renglón se corta antes de una palabra que encabeza un campo («… Ortiz Fecha de ingreso»).
    Un apellido partido en dos renglones se conserva; se corta si lo de abajo es una palabra que nunca es
    nombre, o una que no está en las listas y abre un campo («Observaciones:») o una frase («Presenta
    dolor»)."""
    valor = texto[inicio:fin]
    palabras = list(re.finditer(r"\w+", valor))
    for m in palabras[1:]:
        if _norm(m[0]) in _ENCABEZAN_CAMPO:
            valor = valor[: m.start()].rstrip()
            break
    for salto in _SALTO.finditer(valor):
        sigue = re.match(r"\w+", valor[salto.end() :])
        if sigue is None:
            continue
        palabra = _norm(sigue[0])
        conocida = palabra in NOMBRES_DE_PILA or palabra in APELLIDOS
        abre_otra_cosa = _ABRE_OTRA_COSA.match(texto, inicio + salto.end() + len(sigue[0]))
        if palabra in NO_SON_NOMBRE or (not conocida and abre_otra_cosa):
            return valor[: salto.start()]
    return valor


def palabras_de(nombre: str) -> set[str]:
    """Las palabras de un nombre detectado que sirven para reconocerlo cuando se repite."""
    return {
        p
        for p in re.findall(r"[a-z]+", _norm(nombre))
        if len(p) >= 3 and p not in NO_SON_NOMBRE and p not in {"del", "las", "los"}
    }
