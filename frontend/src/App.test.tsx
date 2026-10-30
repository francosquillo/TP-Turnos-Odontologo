import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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

describe("App C-07 lista de espera", () => {
  afterEach(() => {
    window.history.pushState({}, "", "/");
    vi.unstubAllGlobals();
  });

  it("la URL publica /lista-espera/:token abre la oferta sin sesion", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "token inexistente" }), { status: 404 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    window.history.pushState({}, "", "/lista-espera/tok-url");
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toMatch(/la oferta ya no existe/i);
    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/lista-espera\/oferta\/tok-url$/);
  });

  it("la pestana Lista de espera exige sesion (muestra el login, no la cola)", () => {
    render(<App />);
    within(screen.getByRole("navigation")).getByRole("button", { name: "Lista de espera" }).click();
    expect(screen.queryByRole("list", { name: /lista de espera/i })).toBeNull();
  });
});
