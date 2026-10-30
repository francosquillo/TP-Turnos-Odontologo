import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("App C-08 odontograma", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const TURNO = {
    id: 1, inicio: "2026-10-12T11:00:00Z", fin: "2026-10-12T11:30:00Z", estado: "confirmado",
    paciente_id: 42, paciente_nombre: "Paciente Ficticia", profesional_id: 1,
    profesional_matricula: "DEMO-1", sillon_id: 1, sillon_nombre: "Sillón 1",
  };

  function stubSesion(rol: string): ReturnType<typeof vi.fn> {
    const json = (cuerpo: unknown): Response =>
      new Response(JSON.stringify(cuerpo), { status: 200, headers: { "Content-Type": "application/json" } });
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      const ruta = String(url);
      if (ruta.endsWith("/auth/refresh")) return Promise.resolve(json({ access_token: "t", token_type: "bearer" }));
      if (ruta.endsWith("/auth/me")) return Promise.resolve(json({ id: 1, email: "u@demo.test", nombre: "U", rol }));
      if (ruta.includes("/agenda")) return Promise.resolve(json([TURNO]));
      if (ruta.includes("/historias?paciente_id=")) return Promise.resolve(json([]));
      if (ruta.endsWith("/odontograma/catalogo")) {
        return Promise.resolve(json({ version: 1, estados: [{ codigo: "caries", nombre: "Caries", alcance: "cualquiera" }] }));
      }
      return Promise.resolve(json([]));
    });
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("la agenda abre el odontograma del paciente del turno (odontologo)", async () => {
    const fetchMock = stubSesion("odontologo");
    const usuario = userEvent.setup();
    render(<App />);
    await usuario.click(within(screen.getByRole("navigation")).getByRole("button", { name: "Agenda" }));
    await usuario.click(await screen.findByRole("button", { name: /odontograma/i }));
    expect(await screen.findByRole("heading", { name: /Odontograma · Paciente Ficticia/ })).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes("/historias?paciente_id=42"))).toBe(true);
    expect(await screen.findByRole("button", { name: /abrir historia/i })).toBeDefined();
  });

  it("la secretaria tambien lo abre pero sin poder crear la historia", async () => {
    stubSesion("secretaria");
    const usuario = userEvent.setup();
    render(<App />);
    await usuario.click(within(screen.getByRole("navigation")).getByRole("button", { name: "Agenda" }));
    await usuario.click(await screen.findByRole("button", { name: /odontograma/i }));
    expect(await screen.findByText(/no tiene historia clínica/i)).toBeDefined();
    expect(screen.queryByRole("button", { name: /abrir historia/i })).toBeNull();
  });

  it("el admin no ve el acceso al odontograma en la agenda", async () => {
    stubSesion("admin");
    const usuario = userEvent.setup();
    render(<App />);
    await usuario.click(within(screen.getByRole("navigation")).getByRole("button", { name: "Agenda" }));
    await screen.findByText("Paciente Ficticia");
    expect(screen.queryByRole("button", { name: /odontograma/i })).toBeNull();
  });
});
