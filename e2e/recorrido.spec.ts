import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const CLAVE = "Recorrido-De-Prueba-2026";
const correo = `persona.${Date.now()}@ejemplo.co`;

/** La foto de un documento inventado: el propio navegador la dibuja, con letra grande para el OCR. */
async function fotoDeLaboratorio(page: Page): Promise<Buffer> {
  const hoja = await page.context().newPage();
  await hoja.setViewportSize({ width: 1100, height: 760 });
  await hoja.setContent(`<body style="margin:0;background:#fff;color:#000;font:40px Arial;padding:60px;line-height:2">
    <div>LABORATORIO CLINICO DE PRUEBA</div>
    <div>Paciente: Persona Inventada Rojas</div>
    <div>Fecha: 12/11/2026</div>
    <div>Hemoglobina 13,2 g/dL (ref 12,0 - 15,5)</div>
    <div>Glucosa 92 mg/dL (ref 70 - 100)</div>
    <div>Control en 3 meses con medicina interna</div>
  </body>`);
  const foto = await hoja.screenshot({ type: "png" });
  await hoja.close();
  return foto;
}

const enLaBase = (consulta: string) =>
  execFileSync("docker", ["exec", "medtender-e2e-postgres-1", "psql", "-U", "medtender", "-d", "medtender", "-tAc", consulta], {
    encoding: "utf8",
  }).trim();

test("una persona se registra, sube una foto, la entiende, se lleva sus datos y borra su cuenta", async ({ page, request }) => {
  await test.step("crea su cuenta", async () => {
    await page.goto("/registro");
    await page.getByLabel("Tu nombre").fill("Persona Inventada");
    await page.getByLabel("Correo electrónico").fill(correo);
    await page.getByLabel("Contraseña (mínimo 10 caracteres)").fill(CLAVE);
    await page.getByRole("button", { name: "Crear cuenta" }).click();
    await expect(page.getByRole("button", { name: "Abrir expediente" }).first()).toBeVisible();
  });

  await test.step("abre un expediente", async () => {
    await page.getByRole("button", { name: "Abrir expediente" }).first().click();
    const dialogo = page.getByRole("dialog");
    await dialogo.getByLabel("Código").fill("MIS-EXAMENES");
    await dialogo.getByLabel("Título").fill("Mis exámenes");
    await dialogo.getByRole("button", { name: /Abrir expediente|Crear/ }).click();
    await expect(page).toHaveURL(/\/expedientes\//);
  });

  await test.step("acepta un consentimiento que dice qué proveedor de IA está activo", async () => {
    // El agente de esta prueba usa la API gratuita: el texto debe decirlo y no prometer otra cosa.
    await expect(page.getByText(/versión gratuita, y Google puede conservar y usar lo que se le envía/)).toBeVisible();
    await expect(page.getByText("Versión 2026-11-v3")).toBeVisible();
    await page.getByRole("button", { name: /Entiendo y acepto/ }).click();
    await expect(page.getByRole("heading", { name: /Antes de usar tus documentos/ })).toBeHidden();
  });

  await test.step("sube la foto y se indexa", async () => {
    await page.locator('input[type="file"]').first().setInputFiles({
      name: "laboratorio.png",
      mimeType: "image/png",
      buffer: await fotoDeLaboratorio(page),
    });
    await page.getByRole("button", { name: "Cargar", exact: true }).click();
    await expect(page.getByRole("button", { name: "Explícame este documento" })).toBeVisible({ timeout: 180_000 });
  });

  await test.step("pide la explicación y ve la cita del documento", async () => {
    await page.getByRole("button", { name: "Explícame este documento" }).click();
    await expect(page.getByText(/Hemoglobina 13,2/).first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Resultados de un laboratorio.")).toBeVisible();
  });

  await test.step("a la IA no le llegó el nombre de la persona del documento", async () => {
    const { textos } = (await (await request.get("http://127.0.0.1:18900/peticiones")).json()) as { textos: string[] };
    expect(textos.join("\n")).toContain("Hemoglobina");
    expect(textos.join("\n")).not.toContain("Persona Inventada Rojas");
  });

  await test.step("arma la línea de tiempo", async () => {
    await page.getByRole("button", { name: /línea de tiempo/i }).first().click();
    await expect(page.getByText(/Control en 3 meses/).first()).toBeVisible({ timeout: 60_000 });
  });

  await test.step("prepara la cita con preguntas para su médico", async () => {
    await page.getByRole("button", { name: "Preparar mi cita" }).click();
    await expect(page.getByText("¿Cuándo debo repetir estos exámenes?").first()).toBeVisible({ timeout: 60_000 });
  });

  await test.step("confirma un recordatorio propuesto por el documento", async () => {
    await page.getByRole("button", { name: "Buscar controles en mis documentos" }).click();
    await expect(page).toHaveURL(/\/recordatorios/, { timeout: 60_000 });
    await expect(page.getByText(/Control en 3 meses/).first()).toBeVisible();
    await page.getByRole("button", { name: "Confirmar" }).first().click();
    await expect(page.getByRole("heading", { name: "Próximos" })).toBeVisible();
  });

  await test.step("el historial quedó cifrado en la base", async () => {
    expect(Number(enLaBase("select count(*) from consultas"))).toBeGreaterThan(0);
    expect(enLaBase("select count(*) from consultas where pregunta not like 'mtd1:%' or not respuesta ? 'cifrado'")).toBe("0");
  });

  await test.step("descarga sus datos", async () => {
    await page.goto("/cuenta/datos");
    await page.getByLabel("Contraseña").fill(CLAVE);
    const espera = page.waitForEvent("download");
    await page.getByRole("button", { name: "Descargar mis datos" }).click();
    const descarga = await espera;
    expect(descarga.suggestedFilename()).toMatch(/^medtender-mis-datos-.*\.zip$/);
    const zip = readFileSync(await descarga.path());
    expect(zip.subarray(0, 2).toString()).toBe("PK");
    for (const nombre of ["datos.json", "resumen.html", "LEEME.txt"]) expect(zip.includes(nombre)).toBe(true);
  });

  await test.step("elimina su cuenta y no queda nada", async () => {
    await page.getByRole("button", { name: /Persona Inventada|Menú de usuario|Cuenta/ }).first().click();
    await page.getByRole("menuitem", { name: "Eliminar mi cuenta" }).click();
    await page.getByLabel("Escribe tu contraseña para confirmar").fill(CLAVE);
    await page.getByRole("button", { name: "Eliminar para siempre" }).click();
    await expect.poll(() => enLaBase(`select count(*) from usuarios where email = '${correo}'`)).toBe("0");
    expect(enLaBase("select (select count(*) from fragmentos) + (select count(*) from consultas) + (select count(*) from recordatorios)")).toBe("0");
  });
});
