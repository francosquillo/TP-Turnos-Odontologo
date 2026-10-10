import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App shell C-01 + landing C-05", () => {
  it("renderiza la navegacion y la landing publica por defecto", () => {
    render(<App />);
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("button", { name: "Reservar" })).toBeDefined();
    expect(within(nav).getByRole("button", { name: "Confirmar" })).toBeDefined();
    expect(within(nav).getByRole("button", { name: "Seguridad" })).toBeDefined();
  });

  it("la landing publica enlaza reservas y seguridad", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: /turnos odontol/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /reservar turno/i })).toBeDefined();
  });
});
