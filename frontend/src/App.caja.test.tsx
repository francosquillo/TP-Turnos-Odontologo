import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { estadoCaja, recibo } from "./features/caja/testing";

describe("App C-10 caja", () => {
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
      if (ruta.endsWith("/caja")) return Promise.resolve(json(estadoCaja()));
      if (ruta.includes("/recibos?fecha=")) return Promise.resolve(json([recibo({ numero: 5 })]));
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  const irACaja = async (): Promise<void> => {
    await userEvent.click(within(screen.getByRole("navigation")).getByRole("button", { name: "Caja" }));
  };

  it.each(["secretaria", "admin"])("%s entra a la caja y ve la fecha, el total y los recibos", async (rol) => {
    const fetchMock = stubSesion(rol);
    render(<App />);
    await irACaja();
    expect(await screen.findByRole("heading", { name: /Caja del 31\/10\/2026/ })).toBeDefined();
    expect(await screen.findByText(/Recibo N° 5/)).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/caja"))).toBe(true);
  });

  it("la secretaria ve el cierre y el admin no", async () => {
    stubSesion("secretaria");
    const { unmount } = render(<App />);
    await irACaja();
    expect(await screen.findByRole("form", { name: "Cerrar caja" })).toBeDefined();
    unmount();
    vi.unstubAllGlobals();
    stubSesion("admin");
    render(<App />);
    await irACaja();
    await screen.findByText("Caja abierta");
    expect(screen.queryByRole("form", { name: "Cerrar caja" })).toBeNull();
  });

  it("el odontologo no accede a la pantalla", async () => {
    const fetchMock = stubSesion("odontologo");
    render(<App />);
    await irACaja();
    expect(await screen.findByText("sin permiso")).toBeDefined();
    expect(screen.queryByRole("heading", { name: /Caja del/ })).toBeNull();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/caja"))).toBe(false);
  });
});
