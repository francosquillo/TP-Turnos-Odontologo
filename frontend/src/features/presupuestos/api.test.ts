import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import {
  aceptarPresupuesto,
  crearPresupuesto,
  darDeBajaPresupuesto,
  listarPresupuestos,
  listarTratamientos,
  obtenerPresupuesto,
  presentarPresupuesto,
  rechazarPresupuesto,
  reemplazarItems,
} from "./api";
import { presupuesto, respuestaJson, TRATAMIENTOS } from "./testing";

const ITEMS = [{ hallazgo_id: 11, tratamiento_id: 2, cantidad: 2 }];

function fetchCon(respuesta: Response) {
  return vi.fn().mockResolvedValue(respuesta);
}

function llamada(fetchFn: ReturnType<typeof vi.fn>, n = 0): { url: string; init: RequestInit } {
  const [url, init] = fetchFn.mock.calls[n] as [string, RequestInit | undefined];
  return { url, init: init ?? {} };
}

describe("api de presupuestos", () => {
  it("crear: POST con paciente e items; nada reservado al servidor", async () => {
    const creado = presupuesto();
    const fetchFn = fetchCon(respuestaJson(creado, 201));
    expect(await crearPresupuesto(3, ITEMS, fetchFn)).toEqual(creado);
    const { url, init } = llamada(fetchFn);
    expect(url.endsWith("/presupuestos")).toBe(true);
    expect(init.method).toBe("POST");
    const cuerpo = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(cuerpo).toEqual({ paciente_id: 3, items: ITEMS });
    for (const reservado of ["profesional_id", "estado", "total", "precio"]) {
      expect(cuerpo).not.toHaveProperty(reservado);
    }
  });

  it("listar: pide por paciente y, opcionalmente, por estado", async () => {
    const fetchFn = fetchCon(respuestaJson([presupuesto(), presupuesto({ estado: "aceptado" })]));
    expect(await listarPresupuestos(3, undefined, fetchFn)).toHaveLength(2);
    expect(llamada(fetchFn).url.endsWith("/presupuestos?paciente_id=3")).toBe(true);
    const otro = fetchCon(respuestaJson([]));
    expect(await listarPresupuestos(3, "rechazado", otro)).toEqual([]);
    expect(llamada(otro).url.endsWith("/presupuestos?paciente_id=3&estado=rechazado")).toBe(true);
  });

  it("detalle: GET por id", async () => {
    const p = presupuesto({ id: 9 });
    const fetchFn = fetchCon(respuestaJson(p));
    expect(await obtenerPresupuesto(9, fetchFn)).toEqual(p);
    expect(llamada(fetchFn).url.endsWith("/presupuestos/9")).toBe(true);
  });

  it("detalle: acepta pieza, cara y motivo nulos (vista financiera del admin)", async () => {
    const p = presupuesto({ items: [{ ...presupuesto().items[0]!, pieza_fdi: null, cara: null }] });
    const fetchFn = fetchCon(respuestaJson(p));
    const leido = await obtenerPresupuesto(p.id, fetchFn);
    expect(leido.items[0]?.pieza_fdi).toBeNull();
  });

  it("reemplazar: PUT con la lista completa", async () => {
    const fetchFn = fetchCon(respuestaJson(presupuesto({ id: 4 })));
    await reemplazarItems(4, ITEMS, fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(url.endsWith("/presupuestos/4")).toBe(true);
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({ items: ITEMS });
  });

  it("presentar y aceptar: POST sin cuerpo con datos", async () => {
    const presentado = fetchCon(respuestaJson(presupuesto({ estado: "presentado" })));
    expect((await presentarPresupuesto(4, presentado)).estado).toBe("presentado");
    expect(llamada(presentado).url.endsWith("/presupuestos/4/presentar")).toBe(true);
    const aceptado = fetchCon(respuestaJson(presupuesto({ estado: "aceptado" })));
    expect((await aceptarPresupuesto(4, aceptado)).estado).toBe("aceptado");
    const { url, init } = llamada(aceptado);
    expect(url.endsWith("/presupuestos/4/aceptar")).toBe(true);
    expect(init.method).toBe("POST");
  });

  it("rechazar: el motivo viaja en el cuerpo, nunca en la URL", async () => {
    const fetchFn = fetchCon(respuestaJson(presupuesto({ estado: "rechazado", motivo_rechazo: "Muy caro" })));
    const p = await rechazarPresupuesto(4, "Muy caro", fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(p.motivo_rechazo).toBe("Muy caro");
    expect(url).not.toContain("caro");
    expect(JSON.parse(String(init.body))).toEqual({ motivo: "Muy caro" });
  });

  it("baja: el motivo viaja en el cuerpo como motivo_baja", async () => {
    const fetchFn = fetchCon(respuestaJson(presupuesto()));
    await darDeBajaPresupuesto(4, "Duplicado", fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(url).not.toContain("Duplicado");
    expect(JSON.parse(String(init.body))).toEqual({ motivo_baja: "Duplicado" });
  });

  it("tratamientos: catalogo de solo lectura", async () => {
    const fetchFn = fetchCon(respuestaJson(TRATAMIENTOS));
    expect(await listarTratamientos(fetchFn)).toEqual(TRATAMIENTOS);
    expect(llamada(fetchFn).url.endsWith("/tratamientos")).toBe(true);
  });

  it.each([
    ["estado desconocido", { ...presupuesto(), estado: "anulado" }],
    ["total numerico (el servidor manda texto)", { ...presupuesto(), total: 36000 }],
    ["sin items", { ...presupuesto(), items: undefined }],
    ["item con precio numerico", { ...presupuesto(), items: [{ ...presupuesto().items[0], precio: 18000 }] }],
  ])("forma inesperada: %s", async (_nombre, cuerpo) => {
    await expect(obtenerPresupuesto(1, fetchCon(respuestaJson(cuerpo)))).rejects.toMatchObject({
      message: expect.stringContaining("forma inesperada"),
    });
    await expect(listarPresupuestos(3, undefined, fetchCon(respuestaJson([cuerpo])))).rejects.toBeInstanceOf(ApiError);
  });

  it("un listado que no es lista es una forma inesperada", async () => {
    await expect(listarPresupuestos(3, undefined, fetchCon(respuestaJson({ a: 1 })))).rejects.toBeInstanceOf(ApiError);
    await expect(listarTratamientos(fetchCon(respuestaJson([{ id: "x" }])))).rejects.toBeInstanceOf(ApiError);
  });

  it("409 llega con el mensaje del servidor", async () => {
    const fetchFn = fetchCon(respuestaJson({ detail: "un hallazgo del presupuesto fue corregido o dado de baja" }, 409));
    await expect(aceptarPresupuesto(4, fetchFn)).rejects.toMatchObject({
      httpStatus: 409,
      message: "un hallazgo del presupuesto fue corregido o dado de baja",
    });
    await expect(presentarPresupuesto(4, fetchFn)).rejects.toMatchObject({ httpStatus: 409 });
  });

  it("403 y 422 llegan como ApiError (422 resumido sin datos del paciente)", async () => {
    await expect(
      crearPresupuesto(3, ITEMS, fetchCon(respuestaJson({ detail: "sin turno vigente con el paciente" }, 403))),
    ).rejects.toMatchObject({ httpStatus: 403 });
    await expect(
      crearPresupuesto(3, ITEMS, fetchCon(respuestaJson({ detail: [{ msg: "x", input: "dato" }] }, 422))),
    ).rejects.toMatchObject({ httpStatus: 422, message: "Datos inválidos" });
  });
});
