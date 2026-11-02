import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgendaPage } from "./AgendaPage";

const TURNOS = [
  {
    id: 1,
    inicio: "2026-10-12T11:00:00Z",
    fin: "2026-10-12T11:30:00Z",
    estado: "confirmado",
    paciente_id: 1,
    paciente_nombre: "Demo Paciente",
    profesional_id: 1,
    profesional_matricula: "C04-AG1",
    sillon_id: 1,
    sillon_nombre: "Sillón 1",
  },
  {
    id: 2,
    inicio: "2026-10-12T14:00:00Z",
    fin: "2026-10-12T14:30:00Z",
    estado: "pendiente",
    paciente_id: 2,
    paciente_nombre: "Otra Paciente",
    profesional_id: 1,
    profesional_matricula: "C04-AG1",
    sillon_id: 1,
    sillon_nombre: "Sillón 1",
  },
];

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AgendaPage C-04", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("vista día muestra turnos con color por estado", async () => {
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      if (String(url).includes("/agenda")) {
        return Promise.resolve(respuestaJson(TURNOS, 200));
      }
      return Promise.resolve(respuestaJson([], 200));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AgendaPage />);
    expect(await screen.findByText("Demo Paciente")).toBeDefined();
    expect(await screen.findByText("Otra Paciente")).toBeDefined();
    const confirmado = (await screen.findByText("Demo Paciente")).closest("[data-estado]");
    const pendiente = (await screen.findByText("Otra Paciente")).closest("[data-estado]");
    expect(confirmado?.getAttribute("data-estado")).toBe("confirmado");
    expect(pendiente?.getAttribute("data-estado")).toBe("pendiente");
  });

  it("cancelar sin motivo bloquea el submit", async () => {
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      if (String(url).includes("/agenda")) {
        return Promise.resolve(respuestaJson(TURNOS, 200));
      }
      return Promise.resolve(respuestaJson([], 200));
    });
    vi.stubGlobal("fetch", fetchMock);

    const usuario = userEvent.setup();
    render(<AgendaPage />);
    const botones = await screen.findAllByRole("button", { name: /cancelar/i });
    await usuario.click(botones[0]);
    const botonConfirmar = await screen.findByRole("button", { name: /confirmar cancelación/i });
    expect((botonConfirmar as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock.mock.calls.filter(([url, init]) =>
      String(url).includes("/estado") && (init as RequestInit)?.method === "PATCH",
    )).toHaveLength(0);
  });

  it("con alAbrirOdontograma cada turno ofrece el acceso y lo invoca con el paciente correcto", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(respuestaJson(TURNOS, 200))),
    );
    const alAbrir = vi.fn();
    const usuario = userEvent.setup();
    render(<AgendaPage alAbrirOdontograma={alAbrir} />);
    const botones = await screen.findAllByRole("button", { name: /odontograma/i });
    expect(botones).toHaveLength(2);
    await usuario.click(botones[1] as HTMLElement);
    expect(alAbrir).toHaveBeenCalledTimes(1);
    expect(alAbrir.mock.calls[0]?.[0]).toMatchObject({ paciente_id: 2, paciente_nombre: "Otra Paciente" });
  });

  it("sin alAbrirOdontograma (admin) no hay acceso al odontograma", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(respuestaJson(TURNOS, 200))),
    );
    render(<AgendaPage />);
    await screen.findByText("Demo Paciente");
    expect(screen.queryByRole("button", { name: /odontograma/i })).toBeNull();
  });

  it("tras cambiar el estado la tarjeta conserva los nombres (C-12 11.4)", async () => {
    // PATCH /turnos/{id}/estado devuelve TurnoOut: sin paciente_nombre ni sillon_nombre.
    const respuestaEstado = {
      id: 1,
      inicio: "2026-10-12T11:00:00Z",
      fin: "2026-10-12T11:30:00Z",
      estado: "asistido",
      paciente_id: 1,
      profesional_id: 1,
      sillon_id: 1,
      origen: "staff",
    };
    const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
      if (String(url).includes("/estado") && init?.method === "PATCH") {
        return Promise.resolve(respuestaJson(respuestaEstado, 200));
      }
      return Promise.resolve(respuestaJson(TURNOS, 200));
    });
    vi.stubGlobal("fetch", fetchMock);
    const usuario = userEvent.setup();
    render(<AgendaPage />);
    await usuario.click(await screen.findByRole("button", { name: "Asistido" }));
    const tarjeta = (await screen.findByText(/^asistido ·/)).closest("article");
    expect(tarjeta?.textContent).toContain("Demo Paciente");
    expect(tarjeta?.textContent).toContain("Sillón 1");
    expect(tarjeta?.textContent).not.toContain("Paciente 1");
  });

  it("si la respuesta trae nombres, prevalecen sobre los de la fila previa", async () => {
    const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
      if (String(url).includes("/estado") && init?.method === "PATCH") {
        return Promise.resolve(
          respuestaJson({ ...TURNOS[0], estado: "asistido", paciente_nombre: "Nombre Nuevo" }, 200),
        );
      }
      return Promise.resolve(respuestaJson(TURNOS, 200));
    });
    vi.stubGlobal("fetch", fetchMock);
    const usuario = userEvent.setup();
    render(<AgendaPage />);
    await usuario.click(await screen.findByRole("button", { name: "Asistido" }));
    expect(await screen.findByText("Nombre Nuevo")).toBeDefined();
  });
});
