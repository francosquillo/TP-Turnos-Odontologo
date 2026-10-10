import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgendaPage } from "./AgendaPage";

const TURNO = {
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
};

const ALTERNATIVAS = [
  { inicio: "2026-10-12T12:00:00Z", fin: "2026-10-12T12:30:00Z" },
  { inicio: "2026-10-12T12:30:00Z", fin: "2026-10-12T13:00:00Z" },
];

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function transferencia(): { setData: (k: string, v: string) => void; getData: (k: string) => string } {
  let dato = "";
  return {
    setData: (_k: string, v: string): void => {
      dato = v;
    },
    getData: (_k: string): string => dato,
  };
}

describe("Reprogramar con rollback C-04", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("ante 409 restaura el horario original y muestra alternativas", async () => {
    const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
      if (String(url).includes("/agenda")) {
        return Promise.resolve(respuestaJson([TURNO], 200));
      }
      if (String(url).includes("/turnos/1") && init?.method === "PATCH") {
        return Promise.resolve(
          respuestaJson({ detail: "hueco ocupado", alternativas: ALTERNATIVAS }, 409),
        );
      }
      return Promise.resolve(respuestaJson({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AgendaPage />);
    const arrastrable = (await screen.findByText("Demo Paciente")).closest("[draggable]");
    expect(arrastrable).not.toBeNull();
    const dt = transferencia();
    fireEvent.dragStart(arrastrable as HTMLElement, { dataTransfer: dt });
    const zona = await screen.findByTestId("zona-reprogramar");
    const entrada = await screen.findByLabelText(/nuevo horario/i);
    fireEvent.change(entrada, { target: { value: "2026-10-12T11:15" } });
    fireEvent.drop(zona, { dataTransfer: dt });

    expect(await screen.findByText(/hueco ocupado/i)).toBeDefined();
    const alternativa = await screen.findByText(
      (_contenido: string, elemento: Element | null): boolean =>
        elemento?.tagName === "LI" &&
        (elemento.textContent ?? "").includes("12:00"),
    );
    expect(alternativa.textContent).toContain("12:30");
    // Rollback: el turno sigue mostrando su horario original.
    const tarjeta = (await screen.findByText("Demo Paciente")).closest("article");
    expect(tarjeta?.textContent).toContain("11:00");
  });
});
