import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

describe("App C-09 cuenta corriente", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const TURNO = {
    id: 1, inicio: "2026-10-12T11:00:00Z", fin: "2026-10-12T11:30:00Z", estado: "confirmado",
    paciente_id: 42, paciente_nombre: "Paciente Ficticia", profesional_id: 1,
    profesional_matricula: "DEMO-1", sillon_id: 1, sillon_nombre: "Sillón 1",
  };
  const CUENTA = { paciente_id: 42, saldo: "500.00", movimientos: [] };

  function stubSesion(rol: string): ReturnType<typeof vi.fn> {
    const json = (cuerpo: unknown): Response =>
      new Response(JSON.stringify(cuerpo), { status: 200, headers: { "Content-Type": "application/json" } });
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      const ruta = String(url);
      if (ruta.endsWith("/auth/refresh")) return Promise.resolve(json({ access_token: "t", token_type: "bearer" }));
      if (ruta.endsWith("/auth/me")) return Promise.resolve(json({ id: 1, email: "u@demo.test", nombre: "U", rol }));
      if (ruta.includes("/agenda")) return Promise.resolve(json([TURNO]));
      if (ruta.endsWith("/cuentas/42")) return Promise.resolve(json(CUENTA));
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  async function irALaAgenda(): Promise<void> {
    await userEvent.click(within(screen.getByRole("navigation")).getByRole("button", { name: "Agenda" }));
  }

  it.each(["secretaria", "admin"])("%s ve el acceso y abre la cuenta del paciente del turno", async (rol) => {
    const fetchMock = stubSesion(rol);
    render(<App />);
    await irALaAgenda();
    await userEvent.click(await screen.findByRole("button", { name: "Cuenta corriente" }));
    expect(await screen.findByRole("heading", { name: /Cuenta corriente · Paciente Ficticia/ })).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/cuentas/42"))).toBe(true);
    expect((await screen.findByRole("status")).textContent).toContain("$ 500,00");
  });

  it("odontologo no lo ve", async () => {
    stubSesion("odontologo");
    render(<App />);
    await irALaAgenda();
    await screen.findByText("Paciente Ficticia");
    expect(screen.queryByRole("button", { name: "Cuenta corriente" })).toBeNull();
    expect(screen.getByRole("button", { name: /odontograma/i })).toBeDefined();
  });

  it("volver regresa a la agenda", async () => {
    stubSesion("secretaria");
    render(<App />);
    await irALaAgenda();
    await userEvent.click(await screen.findByRole("button", { name: "Cuenta corriente" }));
    await userEvent.click(await screen.findByRole("button", { name: "Volver a la agenda" }));
    expect(await screen.findByText("Paciente Ficticia")).toBeDefined();
    expect(screen.queryByRole("heading", { name: /Cuenta corriente/ })).toBeNull();
  });
});
