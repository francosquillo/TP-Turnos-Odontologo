import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App C-12 panel admin", () => {
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
      if (ruta.endsWith("/admin/usuarios")) {
        return Promise.resolve(
          json([{ id: 1, nombre: "Admin Demo", email: "admin@example.com", rol: "admin", activo: true }]),
        );
      }
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  const irAAdmin = async (): Promise<void> => {
    await userEvent.click(within(screen.getByRole("navigation")).getByRole("button", { name: "Admin" }));
  };

  it("el admin ve la gestión de usuarios con la lista del backend", async () => {
    stubSesion("admin");
    render(<App />);
    await irAAdmin();
    expect(await screen.findByRole("heading", { name: "Usuarios" })).toBeDefined();
    expect(await screen.findByText("admin@example.com")).toBeDefined();
  });

  it.each(["secretaria", "odontologo"])("%s ve sin permiso y no pide la lista de usuarios", async (rol) => {
    const fetchMock = stubSesion(rol);
    render(<App />);
    await irAAdmin();
    expect(await screen.findByText("sin permiso")).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Usuarios" })).toBeNull();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/admin/usuarios"))).toBe(false);
  });
});
