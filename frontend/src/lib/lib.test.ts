import { esHeic, esImagen, EXTENSIONES_DOCUMENTO } from "./formato";
import { describe, expect, it } from "vitest";
import { localizarOriginal } from "./carpetaLocal";
import { estadoPaso, etiquetaDocumento, paginas, tamano } from "./formato";
import { mismoHash, sha256Hex } from "./sha256";

const bytes = (t: string) => new TextEncoder().encode(t).buffer as ArrayBuffer;

describe("sha256Hex", () => {
  it("coincide con el vector de prueba estándar", async () => {
    expect(await sha256Hex(bytes("abc"))).toBe(
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    );
    expect(mismoHash("ABC ", "abc")).toBe(true);
  });
});

describe("estado del pipeline", () => {
  it("marca pasos hechos, actual y pendientes", () => {
    expect([0, 1, 2, 3, 4, 5].map((i) => estadoPaso("FRAGMENTANDO", i))).toEqual([
      "hecho", "hecho", "hecho", "actual", "pendiente", "pendiente",
    ]);
    expect(estadoPaso("INDEXADO_Y_PURGADO", 5)).toBe("hecho");
    expect(estadoPaso("RECIBIDO", 0)).toBe("actual");
  });
  it("formatea etiquetas", () => {
    expect(etiquetaDocumento("ADENDA", 2)).toBe("Adenda N° 2");
    expect(etiquetaDocumento("PLIEGO", 0)).toBe("Pliego de condiciones");
    expect(paginas(24, 24)).toBe("pág. 24");
    expect(paginas(24, 25)).toBe("págs. 24–25");
    expect(tamano(5 * 1024 * 1024)).toBe("5,0 MB");
  });
});

// ---------- Carpeta simulada (File System Access API) ----------
function archivo(nombre: string, contenido: string): FileSystemFileHandle {
  const file = new File([contenido], nombre, { lastModified: 1 });
  return { kind: "file", name: nombre, getFile: async () => file } as unknown as FileSystemFileHandle;
}

function carpeta(nombre: string, hijos: (FileSystemFileHandle | FileSystemDirectoryHandle)[]): FileSystemDirectoryHandle {
  return {
    kind: "directory",
    name: nombre,
    async *values() {
      yield* hijos;
    },
  } as unknown as FileSystemDirectoryHandle;
}

describe("localizarOriginal", () => {
  it("encuentra por nombre y verifica la huella", async () => {
    const hash = await sha256Hex(bytes("pliego v1"));
    const raiz = carpeta("pdfs", [archivo("otro.pdf", "x"), carpeta("2027", [archivo("Pliego.pdf", "pliego v1")])]);
    const r = await localizarOriginal(raiz, "Pliego.pdf", hash);
    expect(r.tipo).toBe("coincide");
    if (r.tipo === "coincide") {
      expect(r.porNombre).toBe(true);
      expect(r.pdf.ruta).toBe("2027/Pliego.pdf");
    }
  });

  it("encuentra un original renombrado por su contenido", async () => {
    const hash = await sha256Hex(bytes("pliego v1"));
    const raiz = carpeta("pdfs", [archivo("pliego_final_FIRMADO.pdf", "pliego v1"), archivo("notas.txt", "pliego v1")]);
    const r = await localizarOriginal(raiz, "Pliego.pdf", hash);
    expect(r.tipo === "coincide" && !r.porNombre && r.pdf.ruta).toBe("pliego_final_FIRMADO.pdf");
  });

  it("advierte cuando el archivo con ese nombre cambió", async () => {
    const hash = await sha256Hex(bytes("pliego v1"));
    const r = await localizarOriginal(carpeta("pdfs", [archivo("Pliego.pdf", "pliego v2 modificado")]), "Pliego.pdf", hash);
    expect(r.tipo).toBe("distinto");
  });

  it("informa si no existe", async () => {
    const r = await localizarOriginal(carpeta("pdfs", []), "Pliego.pdf", "0".repeat(64));
    expect(r.tipo).toBe("no-encontrado");
  });
});

describe("documentos: PDF y fotos", () => {
  it("reconoce las extensiones aceptadas sin distinguir mayúsculas", () => {
    for (const n of ["a.pdf", "A.PDF", "foto.jpg", "foto.JPEG", "scan.png", "iphone.HEIC", "x.heif"]) {
      expect(EXTENSIONES_DOCUMENTO.test(n)).toBe(true);
    }
    for (const n of ["animacion.gif", "nota.txt", "pdf", "archivo.pdf.exe"]) {
      expect(EXTENSIONES_DOCUMENTO.test(n)).toBe(false);
    }
  });

  it("distingue las fotos de los PDF y las que el navegador no puede mostrar", () => {
    expect(esImagen("resultado.png")).toBe(true);
    expect(esImagen("pliego.pdf")).toBe(false);
    expect(esHeic("IMG_0001.HEIC")).toBe(true);
    expect(esHeic("foto.jpg")).toBe(false);
  });
});
