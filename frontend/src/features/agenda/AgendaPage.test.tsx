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
});
