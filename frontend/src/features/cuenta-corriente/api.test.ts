import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import { anularMovimiento, consultarCuenta } from "./api";
import { cuenta, movimiento, respuestaJson } from "./testing";

function fetchCon(respuesta: Response) {
  return vi.fn().mockResolvedValue(respuesta);
}

function llamada(fetchFn: ReturnType<typeof vi.fn>): { url: string; init: RequestInit } {
  const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit | undefined];
  return { url, init: init ?? {} };
}

describe("api de cuenta corriente", () => {
  it("consultar: GET por paciente; el saldo queda como texto decimal", async () => {
    const dato = cuenta({ saldo: "500.00" });
    const fetchFn = fetchCon(respuestaJson(dato));
    const leida = await consultarCuenta(3, fetchFn);
    expect(leida).toEqual(dato);
    expect(typeof leida.saldo).toBe("string");
    expect(llamada(fetchFn).url.endsWith("/cuentas/3")).toBe(true);
  });

  it("consultar: acepta una cuenta vacia y un saldo a favor negativo", async () => {
    expect(await consultarCuenta(3, fetchCon(respuestaJson(cuenta({ saldo: "0.00", movimientos: [] }))))).toMatchObject({
      saldo: "0.00",
      movimientos: [],
    });
    expect((await consultarCuenta(3, fetchCon(respuestaJson(cuenta({ saldo: "-200.50" }))))).saldo).toBe("-200.50");
  });

  it("anular: POST con el motivo en el cuerpo, nunca en la URL", async () => {
    const anulacion = movimiento({ id: 9, tipo: "ajuste", monto: "-36000.00", anula_a_id: 4, motivo: "Cargado por error" });
    const fetchFn = fetchCon(respuestaJson(anulacion, 201));
    const creado = await anularMovimiento(3, 4, "Cargado por error", fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(creado.anula_a_id).toBe(4);
    expect(url.endsWith("/cuentas/3/movimientos/4/anular")).toBe(true);
    expect(url).not.toContain("error");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ motivo: "Cargado por error" });
  });

  it.each([
    ["saldo numerico (el servidor manda texto)", { ...cuenta(), saldo: 500 }],
    ["tipo desconocido", cuenta({ movimientos: [{ ...movimiento(), tipo: "devolucion" as never }] })],
    ["monto numerico", { ...cuenta(), movimientos: [{ ...movimiento(), monto: 36000 }] }],
    ["sin movimientos", { paciente_id: 3, saldo: "0.00" }],
    ["anulado ausente", { ...cuenta(), movimientos: [{ ...movimiento(), anulado: undefined }] }],
  ])("forma inesperada: %s", async (_nombre, cuerpo) => {
    await expect(consultarCuenta(3, fetchCon(respuestaJson(cuerpo)))).rejects.toMatchObject({
      message: expect.stringContaining("forma inesperada"),
    });
  });

  it("anular: una respuesta con forma inesperada es un error", async () => {
    await expect(anularMovimiento(3, 4, "x", fetchCon(respuestaJson({ id: "no" }, 201)))).rejects.toBeInstanceOf(ApiError);
  });

  it("403 (sin permiso) y 409 (ya anulado) llegan con el mensaje del servidor", async () => {
    await expect(
      consultarCuenta(3, fetchCon(respuestaJson({ detail: "sin permiso" }, 403))),
    ).rejects.toMatchObject({ httpStatus: 403, message: "sin permiso" });
    await expect(
      anularMovimiento(3, 4, "x", fetchCon(respuestaJson({ detail: "el cargo ya fue anulado" }, 409))),
    ).rejects.toMatchObject({ httpStatus: 409, message: "el cargo ya fue anulado" });
  });
});
