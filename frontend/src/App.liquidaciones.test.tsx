import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { liquidacion, obraSocial } from "./features/liquidaciones/testing";

describe("App C-11 liquidaciones", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function stubSesion(rol: string): ReturnType<typeof vi.fn> {
    const json = (cuerpo: unknown): Response =>
      new Response(JSON.stringify(cuerpo), { status: 200, headers: { "Content-Type": "application/json" } });
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      const ruta = String(url);
      if (ruta.endsWith("/auth/refresh")) return Promise.resolve(json({ access_token: "t", token_type: "bearer" }));
      if (ruta.endsWith("/auth/me")) return Promise.resolve(json({ id: 1, email: "u@demo.test", nombre: "U", rol }));
      if (ruta.endsWith("/liquidaciones")) return Promise.resolve(json([liquidacion()]));
      if (ruta.endsWith("/obras-sociales")) return Promise.resolve(json([obraSocial()]));
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  const irALiquidaciones = async (): Promise<void> => {
    await userEvent.click(within(screen.getByRole("navigation")).getByRole("button", { name: "Liquidaciones" }));
  };

  it("el admin entra, ve la lista y el formulario para generar", async () => {
    const fetchMock = stubSesion("admin");
    render(<App />);
    await irALiquidaciones();
    expect(await screen.findByRole("heading", { name: /Liquidaciones a obras sociales/ })).toBeDefined();
    expect(await screen.findByRole("form", { name: "Generar liquidación" })).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/liquidaciones"))).toBe(true);
  });

  it("el odontologo ve la lista pero no el formulario ni pide el catalogo de obras sociales", async () => {
    const fetchMock = stubSesion("odontologo");
    render(<App />);
    await irALiquidaciones();
    expect(await screen.findByRole("heading", { name: /Liquidaciones a obras sociales/ })).toBeDefined();
    expect(screen.queryByRole("form", { name: "Generar liquidación" })).toBeNull();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/obras-sociales"))).toBe(false);
  });

  it("la secretaria no accede a la pantalla ni se hacen pedidos de liquidaciones", async () => {
    const fetchMock = stubSesion("secretaria");
    render(<App />);
    await irALiquidaciones();
    expect(await screen.findByText("sin permiso")).toBeDefined();
    expect(screen.queryByRole("heading", { name: /Liquidaciones a obras sociales/ })).toBeNull();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/liquidaciones"))).toBe(false);
  });
});
