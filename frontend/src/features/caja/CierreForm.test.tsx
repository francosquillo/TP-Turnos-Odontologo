import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CierreForm } from "./CierreForm";
import { caja, respuestaJson } from "./testing";

const CERRADA = caja({
  estado: "cerrada", total_contado: "1500.00", diferencia: "0.00", cerrada_por: 2,
  cerrada_at: "2026-10-31T22:00:00Z",
});

function montar(fetchMock: ReturnType<typeof vi.fn>): { alCerrada: ReturnType<typeof vi.fn> } {
  vi.stubGlobal("fetch", fetchMock);
  const alCerrada = vi.fn().mockResolvedValue(undefined);
  render(<CierreForm cajaId={7} alCerrada={alCerrada} />);
  return { alCerrada };
}

const cuerpos = (fetchMock: ReturnType<typeof vi.fn>): unknown[] =>
  fetchMock.mock.calls.map((c) => JSON.parse(String((c[1] as RequestInit).body)) as unknown);

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CierreForm", () => {
  it("envia caja_id y el contado como texto, y despues refresca desde el servidor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(CERRADA));
    const { alCerrada } = montar(fetchMock);
    await userEvent.type(screen.getByLabelText("Total contado"), "1500.00");
    await userEvent.click(screen.getByRole("button", { name: "Cerrar caja" }));
    expect(cuerpos(fetchMock)).toEqual([{ caja_id: 7, total_contado: "1500.00" }]);
    expect(typeof (cuerpos(fetchMock)[0] as { total_contado: unknown }).total_contado).toBe("string");
    expect(alCerrada).toHaveBeenCalledTimes(1);
  });

  it.each(["", "abc", "-5", "10.123", "1,50"])("el importe invalido %j no se envia", async (texto) => {
    const fetchMock = vi.fn();
    montar(fetchMock);
    if (texto !== "") await userEvent.type(screen.getByLabelText("Total contado"), texto);
    await userEvent.click(screen.getByRole("button", { name: "Cerrar caja" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect((await screen.findByRole("alert")).textContent).toMatch(/importe/i);
  });

  it("el cero es un contado valido", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(CERRADA));
    montar(fetchMock);
    await userEvent.type(screen.getByLabelText("Total contado"), "0");
    await userEvent.click(screen.getByRole("button", { name: "Cerrar caja" }));
    expect(cuerpos(fetchMock)).toEqual([{ caja_id: 7, total_contado: "0" }]);
  });

  it("un 422 por diferencia pide el motivo sin perder el importe; luego lo envia", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respuestaJson({ detail: "la diferencia exige un motivo" }, 422))
      .mockResolvedValueOnce(respuestaJson({ ...CERRADA, total_contado: "1400.00", diferencia: "-100.00", motivo_diferencia: "faltante" }));
    const { alCerrada } = montar(fetchMock);
    const importe = screen.getByLabelText("Total contado");
    await userEvent.type(importe, "1400.00");
    await userEvent.click(screen.getByRole("button", { name: "Cerrar caja" }));
    const motivo = await screen.findByLabelText("Motivo de la diferencia");
    expect((screen.getByLabelText("Total contado") as HTMLInputElement).value).toBe("1400.00");
    expect(alCerrada).not.toHaveBeenCalled();
    await userEvent.type(motivo, "faltante");
    await userEvent.click(screen.getByRole("button", { name: "Cerrar caja" }));
    expect(cuerpos(fetchMock)[1]).toEqual({ caja_id: 7, total_contado: "1400.00", motivo_diferencia: "faltante" });
    expect(alCerrada).toHaveBeenCalledTimes(1);
  });

  it("un error del servidor distinto de la diferencia se muestra y no cierra", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson({ detail: "la caja ya está cerrada" }, 409));
    const { alCerrada } = montar(fetchMock);
    await userEvent.type(screen.getByLabelText("Total contado"), "10");
    await userEvent.click(screen.getByRole("button", { name: "Cerrar caja" }));
    expect((await screen.findByRole("alert")).textContent).toContain("la caja ya está cerrada");
    expect(screen.queryByLabelText("Motivo de la diferencia")).toBeNull();
    expect(alCerrada).not.toHaveBeenCalled();
  });

  it("el boton se deshabilita mientras envia (sin doble envio)", async () => {
    let resolver: (r: Response) => void = () => undefined;
    const fetchMock = vi.fn().mockReturnValue(new Promise<Response>((res) => { resolver = res; }));
    montar(fetchMock);
    await userEvent.type(screen.getByLabelText("Total contado"), "10");
    const boton = screen.getByRole("button", { name: "Cerrar caja" });
    await userEvent.click(boton);
    expect((boton as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(boton);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolver(respuestaJson(CERRADA));
    });
  });
});
