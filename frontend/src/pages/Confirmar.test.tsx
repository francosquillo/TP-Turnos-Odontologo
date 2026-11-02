import { StrictMode } from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Confirmar } from "./Confirmar";
import { Inicio } from "./Inicio";

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Confirmar C-05", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("token valido muestra exito", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          respuestaJson(
            {
              estado: "confirmado",
              inicio: "2026-10-12T12:00:00+00:00",
              fin: "2026-10-12T12:30:00+00:00",
              profesional_id: 1,
            },
            200,
          ),
        ),
      ),
    );
    render(<Confirmar token="tok-valido" />);
    expect(await screen.findByText(/turno confirmado/i)).toBeDefined();
  });

  it("token expirado muestra contacto del consultorio", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          respuestaJson({ detail: "token expirado", contacto: "+54 11 4000-0000" }, 410),
        ),
      ),
    );
    render(<Confirmar token="tok-viejo" />);
    expect(await screen.findByText(/venci[oó]/i)).toBeDefined();
    expect(screen.getByText(/\+54 11 4000-0000/)).toBeDefined();
  });

  it("token invalido muestra contacto sin datos clinicos", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(respuestaJson({ detail: "no encontrado" }, 404))),
    );
    render(<Confirmar token="tok-fantasma" />);
    expect(await screen.findByText(/inv[aá]lido/i)).toBeDefined();
    expect(screen.queryByText(/09:00/)).toBeNull();
  });
});

describe("Landing C-05", () => {
  it("inicio publica enlaza reservas y seguridad", () => {
    let pagina: string | null = null;
    render(<Inicio alNavegar={(destino: string): void => { pagina = destino; }} />);
    expect(screen.getByRole("button", { name: /reserv/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /seguridad/i })).toBeDefined();
    expect(pagina).toBeNull();
  });
});

describe("Confirmar StrictMode (C-12 11.2)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("una carga hace una sola peticion aunque el efecto corra dos veces", async () => {
    // El token se consume en la primera respuesta: una segunda peticion daria 410.
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => Promise.resolve(respuestaJson({ estado: "confirmado" }, 200)))
      .mockImplementation(() =>
        Promise.resolve(respuestaJson({ detail: "token expirado", contacto: "+54 11 4000-0000" }, 410)),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <StrictMode>
        <Confirmar token="tok-strict" />
      </StrictMode>,
    );
    expect(await screen.findByText(/turno confirmado/i)).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/venci[oó]/i)).toBeNull();
  });

  it("tokens distintos hacen una peticion cada uno", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(() => Promise.resolve(respuestaJson({ estado: "confirmado" }, 200)));
    vi.stubGlobal("fetch", fetchMock);
    const { rerender } = render(
      <StrictMode>
        <Confirmar token="tok-a" />
      </StrictMode>,
    );
    await screen.findByText(/turno confirmado/i);
    rerender(
      <StrictMode>
        <Confirmar token="tok-b" />
      </StrictMode>,
    );
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
