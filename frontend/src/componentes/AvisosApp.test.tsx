import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AvisosApp, EVENTO_VERSION_NUEVA } from "./AvisosApp";

describe("AvisosApp", () => {
  it("no muestra nada con conexión y sin versión nueva", () => {
    const { container } = render(<AvisosApp alActualizar={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("avisa sin conexión y lo quita al volver", () => {
    render(<AvisosApp alActualizar={() => {}} />);
    act(() => void window.dispatchEvent(new Event("offline")));
    expect(screen.getByText(/Sin conexión/)).toBeInTheDocument();
    act(() => void window.dispatchEvent(new Event("online")));
    expect(screen.queryByText(/Sin conexión/)).not.toBeInTheDocument();
  });

  it("ofrece actualizar cuando hay una versión nueva", () => {
    const alActualizar = vi.fn();
    render(<AvisosApp alActualizar={alActualizar} />);
    act(() => void window.dispatchEvent(new Event(EVENTO_VERSION_NUEVA)));
    fireEvent.click(screen.getByRole("button", { name: "Actualizar" }));
    expect(alActualizar).toHaveBeenCalledOnce();
  });
});
