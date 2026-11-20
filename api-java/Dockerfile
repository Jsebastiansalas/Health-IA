# Etapa 1: compila el jar (sin ejecutar pruebas: corren en CI con Testcontainers).
FROM maven:3.9-eclipse-temurin-21 AS compilacion
WORKDIR /src
COPY pom.xml .
COPY src ./src
# La caché de ~/.m2 sobrevive entre construcciones: un reintento no vuelve a bajar todo.
RUN --mount=type=cache,target=/root/.m2 mvn -q -B -DskipTests package

# Etapa 2: solo el JRE. Usuario sin privilegios con el MISMO uid (1001) que el agente Python, para
# compartir el volumen efímero donde esta API deja el PDF y el agente lo lee y lo borra.
FROM eclipse-temurin:21-jre-alpine
RUN adduser -S -u 1001 medtender \
    && mkdir -p /var/medtender-ephemeral \
    && chown medtender /var/medtender-ephemeral \
    && chmod 700 /var/medtender-ephemeral
COPY --from=compilacion /src/target/api-java-*.jar /app/app.jar
USER medtender
EXPOSE 8080
# El 70 % de la memoria del contenedor para el heap; el resto para hilos, buffers y pdfbox.
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=70", "-XX:+ExitOnOutOfMemoryError", "-jar", "/app/app.jar"]
