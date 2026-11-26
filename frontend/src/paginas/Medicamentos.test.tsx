import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CitaAgregada, CitaFicha, CitaPrecio, CitaRegistro, FuenteDato } from "../api/tipos";
import { FuentesCitadas, FuentesOficiales } from "./Medicamentos";

const fuente: FuenteDato = {
  conjunto: "Código único de medicamentos vigentes",
  datasetId: "i7cb-raxc",
  enlace: "https://www.datos.gov.co/d/i7cb-raxc",
  cargadoAt: "2026-11-19T15:00:00Z",
  licencia: "CC BY-SA 4.0",
};

const registro: CitaRegistro = {
  tipo: "REGISTRO_INVIMA",
  id: "R1",
  cum: "19912345-1",
  producto: "LOSARTAN POTASICO 50 MG TABLETAS",
  titular: "Genfar S.A.",
  registroSanitario: "INVIMA 2024M-0001234",
  estadoRegistro: "Vigente",
  conjunto: "VIGENTE",
  fechaExpedicion: "2020-05-01",
  fechaVencimiento: "3000-01-01",
  atc: "C09CA01",
  descripcionAtc: "Losartán",
  formaFarmaceutica: "Tableta recubierta",
  viaAdministracion: "Oral",
  principiosActivos: [{ nombre: "Losartán potásico", cantidad: "50", unidad: "mg" }],
  presentacion: "Caja x 30",
  presentaciones: 3,
  fuente,
};

const precio: CitaPrecio = {
  tipo: "PRECIO_REGULADO",
  id: "P1",
  cum: "19912345-1",
  medicamento: "LOSARTAN 50 MG",
  precioInstitucional: "1200",
  precioComercial: "1500",
  precioFinalComercial: "1800",
  circular: "Circular 07 de 2024",
  vigenciaDesde: "2024-03-01",
  fuente: { ...fuente, conjunto: "Precio máximo de venta" },
};

const agregada: CitaAgregada = {
  tipo: "CONSULTA_AGREGADA",
  id: "E1",
  filtros: { principio_activo: "metformina" },
  coincidenciasCum: 14,
  registrosSanitarios: 6,
  titularesDistintos: 5,
  porConjunto: [{ conjunto: "VIGENTE", cum: 12, registros: 5 }],
  fuente,
};

describe("FuentesCitadas", () => {
  it("presenta los registros en una tabla con marcador, estado, vencimiento y enlace a la fuente", () => {
    render(<FuentesCitadas citas={[registro]} base="cita-x" resaltada={null} />);
    const tabla = screen.getByRole("table", { name: /registros sanitarios citados/i });
    const fila = within(tabla).getByRole("row", { name: /LOSARTAN POTASICO/ });
    expect(within(fila).getByText("R1")).toBeInTheDocument();
    expect(within(fila).getByText("Genfar S.A.")).toBeInTheDocument();
    expect(within(fila).getByText("Vigente")).toBeInTheDocument();
    expect(within(fila).getByText("Sin vencimiento")).toBeInTheDocument(); // INVIMA usa el año 3000
    expect(within(fila).getByText(/3 presentaciones/)).toBeInTheDocument();
    const enlace = within(fila).getByRole("link", { name: /ver fuente/i });
    expect(enlace).toHaveAttribute("href", "https://www.datos.gov.co/d/i7cb-raxc");
    expect(enlace).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("separa los precios regulados y los formatea en pesos colombianos", () => {
    render(<FuentesCitadas citas={[registro, precio]} base="cita-x" resaltada={null} />);
    const tabla = screen.getByRole("table", { name: /precio máximo regulado/i });
    expect(within(tabla).getByText(/1\.800/)).toBeInTheDocument();
    expect(within(tabla).getByText("Circular 07 de 2024")).toBeInTheDocument();
    expect(screen.getAllByRole("table")).toHaveLength(2);
  });

  it("cada fila lleva el id al que apunta la referencia [R1] de la respuesta y se resalta", () => {
    const { container } = render(<FuentesCitadas citas={[registro]} base="cita-x" resaltada="R1" />);
    const fila = container.querySelector("#cita-x-R1");
    expect(fila).not.toBeNull();
    expect(fila!.className).toContain("bg-cita");
  });

  it("muestra la consulta agregada como ficha, sin tabla", () => {
    render(<FuentesCitadas citas={[agregada]} base="cita-x" resaltada={null} />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("6 registros sanitarios")).toBeInTheDocument();
    expect(screen.getByText(/principio_activo: metformina/)).toBeInTheDocument();
  });

  it("muestra la ficha técnica citada con su sección, el extracto literal y el enlace a la fuente", () => {
    const ficha: CitaFicha = {
      tipo: "FICHA_TECNICA",
      id: "F1",
      medicamento: "IBUPROFENO FALSO 400 MG",
      principioActivo: "ibuprofeno",
      registro: "111",
      seccion: "4.3",
      titulo: "Contraindicaciones",
      extractoLiteral: "- en pacientes con úlcera gástrica",
      extractoTruncado: true,
      fuente: { ...fuente, conjunto: "Ficha técnica (CIMA, AEMPS de España)", enlace: "https://cima.aemps.es/x.html" },
    };
    render(<FuentesCitadas citas={[ficha]} base="cita-x" resaltada="F1" />);
    expect(screen.getByText(/Contraindicaciones · sección 4\.3/)).toBeInTheDocument();
    expect(screen.getByText(/en pacientes con úlcera gástrica/)).toBeInTheDocument();
    expect(screen.getByText(/Extracto recortado/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ver fuente/ })).toHaveAttribute("href", "https://cima.aemps.es/x.html");
    expect(document.getElementById("cita-x-F1")!.className).toContain("ring-cita");
  });

  it("un prospecto que subió la persona se cita como su documento, sin enlace externo", () => {
    const prospecto: CitaFicha = {
      tipo: "FICHA_TECNICA",
      origen: "PROSPECTO",
      id: "F1",
      medicamento: "Ibuprofeno",
      principioActivo: "ibuprofeno",
      registro: null,
      seccion: "pág. 2",
      titulo: "Prospecto",
      extractoLiteral: "No debe usarse en pacientes con úlcera gástrica activa.",
      extractoTruncado: false,
      nombreArchivo: "prospecto_ibuprofeno.pdf",
      paginaInicio: 2,
      fuente: { ...fuente, conjunto: "Tu prospecto: prospecto_ibuprofeno.pdf", datasetId: null, enlace: null, cargadoAt: null, licencia: "Documento que subiste" },
    };
    render(<FuentesCitadas citas={[prospecto]} base="cita-x" resaltada={null} />);
    expect(screen.getByText(/Tu prospecto: prospecto_ibuprofeno\.pdf · pág\. 2/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Ver fuente/ })).not.toBeInTheDocument();
  });

  it("las fuentes oficiales son solo enlaces", () => {
    render(<FuentesOficiales fuentes={[{ nombre: "INVIMA", url: "https://www.invima.gov.co/" }]} />);
    expect(screen.getByRole("link", { name: "INVIMA" })).toHaveAttribute("href", "https://www.invima.gov.co/");
  });

  it("no pinta nada si no hay fuentes citadas", () => {
    render(<FuentesCitadas citas={[]} base="cita-x" resaltada={null} />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
