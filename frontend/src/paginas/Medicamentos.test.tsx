import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CitaAgregada, CitaPrecio, CitaRegistro, FuenteDato } from "../api/tipos";
import { FuentesCitadas } from "./Medicamentos";

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
    expect(fila!.className).toContain("bg-marca");
  });

  it("muestra la consulta agregada como ficha, sin tabla", () => {
    render(<FuentesCitadas citas={[agregada]} base="cita-x" resaltada={null} />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByText("6 registros sanitarios")).toBeInTheDocument();
    expect(screen.getByText(/principio_activo: metformina/)).toBeInTheDocument();
  });

  it("no pinta nada si no hay fuentes citadas", () => {
    render(<FuentesCitadas citas={[]} base="cita-x" resaltada={null} />);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
