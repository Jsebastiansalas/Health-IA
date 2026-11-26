package co.medtender.api.recordatorios;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/** Activa las tareas programadas (el aviso diario de recordatorios). */
@Configuration
@EnableScheduling
public class RecordatoriosConfig {}
