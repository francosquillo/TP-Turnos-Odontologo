import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import { anularRecibo, cerrarCaja, cobrar, consultarCaja, listarRecibos } from "./api";
import { caja, cobro, estadoCaja, recibo, respuestaJson } from "./testing";
import { esImporteValido, formatearFecha } from "./tipos";

const CLAVE = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d";

function fetchCon(respuesta: Response) {
  return vi.fn().mockResolvedValue(respuesta);
}

function llamada(fetchFn: ReturnType<typeof vi.fn>): { url: string; init: RequestInit } {
  const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit | undefined];
  return { url, init: init ?? {} };
}

describe("api de caja", () => {
  it("consultarCaja: GET sin fecha y con fecha; los importes quedan como texto", async () => {
    const dato = estadoCaja();
    const sinFecha = fetchCon(respuestaJson(dato));
    const leido = await consultarCaja(undefined, sinFecha);
    expect(leido).toEqual(dato);
    expect(typeof leido.caja?.total_sistema).toBe("string");
    expect(llamada(sinFecha).url.endsWith("/caja")).toBe(true);
    const conFecha = fetchCon(respuestaJson(estadoCaja({ caja: null, desglose: [] })));
    await consultarCaja("2026-10-30", conFecha);
    expect(llamada(conFecha).url.endsWith("/caja?fecha=2026-10-30")).toBe(true);
  });

  it("consultarCaja: acepta bloqueo y caja nula", async () => {
    const bloqueada = estadoCaja({ operable: false, bloqueo: "caja_pendiente" });
    expect((await consultarCaja(undefined, fetchCon(respuestaJson(bloqueada)))).bloqueo).toBe("caja_pendiente");
    const vacia = estadoCaja({ caja: null, desglose: [] });
    expect((await consultarCaja(undefined, fetchCon(respuestaJson(vacia)))).caja).toBeNull();
  });

  it("listarRecibos: GET con la fecha en la query", async () => {
    const lista = [recibo({ numero: 2 }), recibo({ numero: 1, anulado: true, motivo_anulacion: "error", anulado_por: 1, anulado_at: "2026-10-31T16:00:00Z" })];
    const fetchFn = fetchCon(respuestaJson(lista));
    expect(await listarRecibos("2026-10-31", fetchFn)).toEqual(lista);
    expect(llamada(fetchFn).url.endsWith("/recibos?fecha=2026-10-31")).toBe(true);
  });

  it("cobrar: POST con la clave en el cuerpo; acepta 201 (creado) y 200 (reintento)", async () => {
    const datos = { presupuesto_id: 31, monto: "400.00", medio: "efectivo" as const, clave_idempotencia: CLAVE };
    const creado = fetchCon(respuestaJson(cobro(), 201));
    const r1 = await cobrar(datos, creado);
    const { url, init } = llamada(creado);
    expect(url.endsWith("/caja/cobrar")).toBe(true);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(datos);
    expect(r1.creado).toBe(true);
    const repetido = await cobrar(datos, fetchCon(respuestaJson(cobro(), 200)));
    expect(repetido.creado).toBe(false);
    expect(typeof repetido.cobro.monto).toBe("string");
  });

  it("cerrarCaja: POST con caja_id y el contado como texto; el motivo va en el cuerpo", async () => {
    const cerrada = caja({ estado: "cerrada", total_contado: "1400.00", diferencia: "-100.00", motivo_diferencia: "faltante", cerrada_por: 2, cerrada_at: "2026-10-31T22:00:00Z" });
    const fetchFn = fetchCon(respuestaJson(cerrada));
    const salida = await cerrarCaja({ caja_id: 7, total_contado: "1400.00", motivo_diferencia: "faltante" }, fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(salida.diferencia).toBe("-100.00");
    expect(url.endsWith("/caja/cierre")).toBe(true);
    expect(url).not.toContain("faltante");
    expect(JSON.parse(String(init.body))).toEqual({ caja_id: 7, total_contado: "1400.00", motivo_diferencia: "faltante" });
  });

  it("anularRecibo: POST con el motivo solo en el cuerpo", async () => {
    const anulado = recibo({ id: 9, anulado: true, motivo_anulacion: "cobro duplicado", anulado_por: 1, anulado_at: "2026-10-31T16:00:00Z" });
    const fetchFn = fetchCon(respuestaJson(anulado));
    const salida = await anularRecibo(9, "cobro duplicado", fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(salida.anulado).toBe(true);
    expect(url.endsWith("/recibos/9/anular")).toBe(true);
    expect(url).not.toContain("duplicado");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ motivo: "cobro duplicado" });
  });

  it("un error del servidor conserva el estado y el mensaje", async () => {
    const datos = { presupuesto_id: 31, monto: "9999.00", medio: "efectivo" as const, clave_idempotencia: CLAVE };
    const fallo = cobrar(datos, fetchCon(respuestaJson({ detail: "el importe supera el pendiente" }, 422)));
    await expect(fallo).rejects.toMatchObject({ httpStatus: 422, message: "el importe supera el pendiente" });
  });

  it.each([
    ["importe numerico", { ...estadoCaja(), caja: { ...caja(), total_sistema: 1500 } }],
    ["bloqueo desconocido", { ...estadoCaja(), bloqueo: "otro" }],
    ["medio del desglose desconocido", { ...estadoCaja(), desglose: [{ medio: "tarjeta", subtotal: "1.00" }] }],
    ["sin operable", { fecha: "2026-10-31", hoy: "2026-10-31", bloqueo: null, caja: null, desglose: [] }],
    ["estado de caja desconocido", { ...estadoCaja(), caja: { ...caja(), estado: "reabierta" } }],
  ])("consultarCaja con forma inesperada: %s", async (_nombre, cuerpo) => {
    await expect(consultarCaja(undefined, fetchCon(respuestaJson(cuerpo)))).rejects.toMatchObject({
      message: expect.stringContaining("forma inesperada"),
    });
  });

  it("listarRecibos con forma inesperada es un error", async () => {
    await expect(listarRecibos("2026-10-31", fetchCon(respuestaJson([{ id: "x" }])))).rejects.toBeInstanceOf(ApiError);
    await expect(listarRecibos("2026-10-31", fetchCon(respuestaJson({ lista: [] })))).rejects.toBeInstanceOf(ApiError);
  });

  it("cobrar, cerrarCaja y anularRecibo con forma inesperada son un error", async () => {
    const datos = { presupuesto_id: 31, monto: "1.00", medio: "efectivo" as const, clave_idempotencia: CLAVE };
    await expect(cobrar(datos, fetchCon(respuestaJson({ numero: "uno" }, 201)))).rejects.toBeInstanceOf(ApiError);
    await expect(cerrarCaja({ caja_id: 1, total_contado: "1.00" }, fetchCon(respuestaJson({})))).rejects.toBeInstanceOf(ApiError);
    await expect(anularRecibo(1, "x", fetchCon(respuestaJson({})))).rejects.toBeInstanceOf(ApiError);
  });
});

describe("formatearFecha", () => {
  it("2026-10-31 da 31/10/2026 con cualquier reloj (no pasa por Date, que lo leeria como UTC)", () => {
    vi.useFakeTimers();
    try {
      for (const ahora of ["2026-10-31T02:00:00Z", "2026-11-01T15:00:00Z"]) {
        vi.setSystemTime(new Date(ahora));
        expect(formatearFecha("2026-10-31")).toBe("31/10/2026");
        expect(formatearFecha("2026-01-05")).toBe("05/01/2026");
      }
    } finally {
      vi.useRealTimers();
    }
  });

  it("una fecha con forma inesperada no se inventa", () => {
    expect(formatearFecha("31/10/2026")).toBe("—");
    expect(formatearFecha("")).toBe("—");
  });

  it("acepta un instante ISO y toma el dia del texto", () => {
    expect(formatearFecha("2026-10-31T02:00:00Z")).toBe("31/10/2026");
  });
});

describe("esImporteValido", () => {
  it.each(["0.01", "1", "400", "400.5", "400.50", "1234567.99"])("acepta %s", (texto) => {
    expect(esImporteValido(texto)).toBe(true);
  });

  it.each(["", "0", "0.00", "-1", "1.234", "1,50", "abc", " 5", "5 ", "1e3", ".5", "1."])("rechaza %j", (texto) => {
    expect(esImporteValido(texto)).toBe(false);
  });
});
