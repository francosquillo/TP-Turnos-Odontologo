import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgendaPage } from "./AgendaPage";

const TURNOS = [
  {
    id: 1, inicio: "2026-10-12T11:00:00Z", fin: "2026-10-12T11:30:00Z", estado: "confirmado",
    paciente_id: 1, paciente_nombre: "Demo Paciente", profesional_id: 1,
    profesional_matricula: "C04-AG1", sillon_id: 1, sillon_nombre: "Sillón 1",
  },
  {
    id: 2, inicio: "2026-10-12T14:00:00Z", fin: "2026-10-12T14:30:00Z", estado: "pendiente",
    paciente_id: 2, paciente_nombre: "Otra Paciente", profesional_id: 1,
    profesional_matricula: "C04-AG1", sillon_id: 1, sillon_nombre: "Sillón 1",
  },
];

function stubAgenda(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(TURNOS), { status: 200, headers: { "Content-Type": "application/json" } }),
      ),
    ),
  );
}

describe("AgendaPage con acceso a la cuenta corriente (C-09)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("con alAbrirCuenta cada turno ofrece el acceso y lo invoca con el paciente correcto", async () => {
    stubAgenda();
    const alAbrirCuenta = vi.fn();
    render(<AgendaPage alAbrirCuenta={alAbrirCuenta} />);
    const botones = await screen.findAllByRole("button", { name: "Cuenta corriente" });
    expect(botones).toHaveLength(2);
    await userEvent.click(botones[1] as HTMLElement);
    expect(alAbrirCuenta).toHaveBeenCalledTimes(1);
    expect(alAbrirCuenta.mock.calls[0]?.[0]).toMatchObject({ paciente_id: 2, paciente_nombre: "Otra Paciente" });
  });

  it("sin alAbrirCuenta (odontologo) no hay acceso", async () => {
    stubAgenda();
    render(<AgendaPage alAbrirOdontograma={vi.fn()} />);
    await screen.findByText("Demo Paciente");
    expect(screen.queryByRole("button", { name: "Cuenta corriente" })).toBeNull();
    expect(screen.getAllByRole("button", { name: /odontograma/i })).toHaveLength(2);
  });

  it("ambos accesos conviven cuando la secretaria recibe los dos", async () => {
    stubAgenda();
    render(<AgendaPage alAbrirOdontograma={vi.fn()} alAbrirCuenta={vi.fn()} />);
    await screen.findByText("Demo Paciente");
    expect(screen.getAllByRole("button", { name: "Cuenta corriente" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /odontograma/i })).toHaveLength(2);
  });
});
