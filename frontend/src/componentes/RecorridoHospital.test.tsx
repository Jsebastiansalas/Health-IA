import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RecorridoHospital } from "./RecorridoHospital";

const paradas = Array.from({ length: 6 }, (_, i) => ({ titulo: `Parada ${i + 1}`, texto: `Texto ${i + 1}` }));

describe("RecorridoHospital", () => {
  it("sin pantalla ancha con ratón muestra las seis escenas fijas con su texto, sin videos", () => {
    const { container } = render(<RecorridoHospital titulo="Un día en el hospital" paradas={paradas} />);
    expect(screen.getByRole("heading", { name: "Un día en el hospital" })).toBeInTheDocument();
    paradas.forEach((p) => expect(screen.getByRole("heading", { name: p.titulo })).toBeInTheDocument());
    expect(container.querySelectorAll("img")).toHaveLength(6);
    expect(container.querySelector("video")).toBeNull();
  });
});
