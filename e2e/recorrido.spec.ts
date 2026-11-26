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
  await test.step("la portada carga con sus escenas y sin errores", async () => {
    const errores: string[] = [];
    page.on("pageerror", (e) => errores.push(e.message));
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Entiende los documentos");
    await expect(page.locator("video").first()).toBeAttached({ timeout: 30_000 });
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute("content", /og-portada\.jpg$/);
    expect(errores).toEqual([]);
  });

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
    // A una persona solo se le pide el nombre.
    await dialogo.getByLabel("¿Cómo quieres llamarlo?").fill("Mis exámenes");
    await dialogo.getByRole("button", { name: "Crear expediente" }).click();
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

  await test.step("baja el resumen de la cita en PDF", async () => {
    const espera = page.waitForEvent("download");
    await page.getByRole("button", { name: "Descargar PDF" }).click();
    expect(readFileSync(await (await espera).path()).subarray(0, 5).toString()).toBe("%PDF-");
    await page.keyboard.press("Escape");
  });

  await test.step("confirma un recordatorio propuesto por el documento", async () => {
    await page.getByRole("button", { name: "Buscar controles en mis documentos" }).click();
    await expect(page).toHaveURL(/\/recordatorios/, { timeout: 60_000 });
    await expect(page.getByText(/Control en 3 meses/).first()).toBeVisible();
    await page.getByRole("button", { name: "Confirmar" }).first().click();
    await expect(page.getByRole("heading", { name: "Próximos" })).toBeVisible();
  });

  await test.step("comparte el expediente con un cuidador, que lo ve y luego pierde el acceso", async () => {
    const cuidador = `cuidador.${Date.now()}@ejemplo.co`;
    await page.goto("/");
    await page.getByRole("link", { name: /Mis exámenes/ }).first().click();
    const suyo = page.url();
    await page.getByRole("button", { name: "Compartir con un cuidador" }).click();
    await page.getByLabel("Correo de esa persona").fill(cuidador);
    await page.getByRole("checkbox", { name: /tengo derecho a compartir/i }).check();
    await page.getByRole("button", { name: "Enviar invitación" }).click();
    await expect(page.getByText("Invitación enviada.", { exact: false })).toBeVisible();

    let enlace = "";
    await expect
      .poll(async () => {
        const { correos } = (await (await request.get("http://127.0.0.1:18900/correos")).json()) as {
          correos: { para: string; texto: string }[];
        };
        const correoInvitacion = correos.filter((c) => c.para.includes(cuidador)).pop();
        enlace = correoInvitacion?.texto.match(/\/invitacion\?token=[0-9a-f]{64}/)?.[0] ?? "";
        expect(correoInvitacion?.texto ?? "").not.toContain("Mis exámenes");
        return enlace;
      })
      .not.toBe("");

    // La otra persona, en su propio navegador.
    const otro = await page.context().browser()!.newContext({ baseURL: "http://localhost:18088", serviceWorkers: "block" });
    const suya = await otro.newPage();
    await suya.goto("/registro");
    await suya.getByLabel("Tu nombre").fill("Cuidador Inventado");
    await suya.getByLabel("Correo electrónico").fill(cuidador);
    await suya.getByLabel("Contraseña (mínimo 10 caracteres)").fill(CLAVE);
    await suya.getByRole("button", { name: "Crear cuenta" }).click();
    await expect(suya.getByRole("button", { name: "Abrir expediente" }).first()).toBeVisible();
    await suya.goto(enlace);
    await suya.getByRole("button", { name: "Aceptar invitación" }).click();
    await expect(suya.getByRole("note").first()).toContainText("Persona Inventada te compartió este expediente");
    await expect(suya.getByRole("button", { name: "Explícame este documento" })).toBeVisible();
    await expect(suya.getByRole("button", { name: "Compartir con un cuidador" })).toHaveCount(0);

    await page.keyboard.press("Escape");
    await page.reload();
    await page.getByRole("button", { name: "Compartir con un cuidador" }).click();
    await page.getByRole("button", { name: `Quitar acceso a ${cuidador}` }).click();
    await expect(page.getByText(cuidador)).toHaveCount(0);
    await suya.goto(suyo);
    await expect(suya.getByRole("heading", { name: "Expediente no disponible" })).toBeVisible();
    await otro.close();
    await page.keyboard.press("Escape");
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
    expect(enLaBase("select (select count(*) from fragmentos) + (select count(*) from consultas) + (select count(*) from recordatorios) + (select count(*) from comparticiones)")).toBe("0");
  });
});
