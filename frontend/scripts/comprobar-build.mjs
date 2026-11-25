// Presupuesto del build: lo que la app instalada guarda en el teléfono y lo que pesa la portada.
// Uso: npm run build && npm run comprobar:build
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const dist = new URL("../dist/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const sw = readFileSync(join(dist, "sw.js"), "utf8");
const guardados = [...new Set([...sw.matchAll(/url:"([^"]+)"|"url":"([^"]+)"/g)].map((m) => m[1] ?? m[2]))];
const fallos = [];
if (guardados.length < 10) fallos.push(`no se pudo leer la lista de archivos guardados (${guardados.length})`);

for (const [patron, motivo] of [
  [/^recorrido\//, "los videos de la portada no van al teléfono"],
  [/html2canvas|canvg|purify|index\.es-/i, "jsPDF no debe arrastrar su conversor de HTML (no se usa)"],
  [/rastreo-/, "el rastreo de errores solo se descarga si está activado"],
]) {
  for (const archivo of guardados.filter((a) => patron.test(a))) fallos.push(`${archivo}: ${motivo}`);
}
for (const archivo of readdirSync(join(dist, "assets"))) {
  if (/html2canvas|canvg|purify/i.test(archivo)) fallos.push(`${archivo}: sobra en el build`);
}

const MB = 1024 * 1024;
const video = readdirSync(join(dist, "recorrido"))
  .filter((f) => f.endsWith(".mp4"))
  .reduce((t, f) => t + statSync(join(dist, "recorrido", f)).size, 0);
if (video > 7 * MB) fallos.push(`los videos de la portada pesan ${(video / MB).toFixed(1)} MB (máximo 7)`);

for (const necesario of ["og-portada.jpg"]) {
  try {
    statSync(join(dist, necesario));
  } catch {
    fallos.push(`falta ${necesario}`);
  }
}
const html = readFileSync(join(dist, "index.html"), "utf8");
for (const etiqueta of ['property="og:title"', 'property="og:image"', 'name="twitter:card"']) {
  if (!html.includes(etiqueta)) fallos.push(`index.html sin ${etiqueta}`);
}
if (html.includes("%VITE_")) fallos.push("index.html quedó con variables sin sustituir");

const peso = guardados.reduce((t, a) => {
  try {
    return t + statSync(join(dist, a)).size;
  } catch {
    return t;
  }
}, 0);
for (const f of fallos) console.log(`FALLA  ${f}`);
console.log(`${fallos.length ? "FALLA" : "OK"}  ${guardados.length} archivos en el teléfono (${(peso / MB).toFixed(2)} MB), videos ${(video / MB).toFixed(1)} MB`);
process.exit(fallos.length ? 1 : 0);
