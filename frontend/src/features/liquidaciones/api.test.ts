import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import {
  cobrarLiquidacion,
  descargarInforme,
  descartarLiquidacion,
  generarLiquidacion,
  listarLiquidaciones,
  listarObrasSociales,
  obtenerLiquidacion,
  presentarLiquidacion,
  revertirCobroLiquidacion,
} from "./api";
import { detalle, item, liquidacion, obraSocial, plan, respuestaJson } from "./testing";
import { esPeriodoValido, periodoATexto } from "./tipos";

function fetchCon(respuesta: Response) {
  return vi.fn().mockResolvedValue(respuesta);
}

function llamada(fetchFn: ReturnType<typeof vi.fn>): { url: string; init: RequestInit } {
  const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit | undefined];
  return { url, init: init ?? {} };
}

describe("api de liquidaciones", () => {
  it("listarLiquidaciones: GET; los importes quedan como texto", async () => {
    const lista = [liquidacion(), liquidacion({ id: 8, estado: "cobrada", cobrada_at: "2026-10-31T16:00:00Z" })];
    const fetchFn = fetchCon(respuestaJson(lista));
    const leida = await listarLiquidaciones(fetchFn);
    expect(leida).toEqual(lista);
    expect(typeof leida[0]?.total).toBe("string");
    expect(llamada(fetchFn).url.endsWith("/liquidaciones")).toBe(true);
  });

  it("obtenerLiquidacion: GET por id y filas agrupadas por plan", async () => {
    const dato = detalle({
      planes: [plan({ items: [item({ revision: true, monto: "0.00" })], subtotal: "0.00" })],
      cantidad_revision: 1,
    });
    const fetchFn = fetchCon(respuestaJson(dato));
    const leida = await obtenerLiquidacion(7, fetchFn);
    expect(leida.planes[0]?.items[0]?.revision).toBe(true);
    expect(llamada(fetchFn).url.endsWith("/liquidaciones/7")).toBe(true);
  });

  it("generarLiquidacion: POST con os_id y periodo YYYY-MM en el cuerpo", async () => {
    const fetchFn = fetchCon(respuestaJson(detalle(), 201));
    await generarLiquidacion({ os_id: 1, periodo: "2026-10" }, fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(url.endsWith("/liquidaciones")).toBe(true);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ os_id: 1, periodo: "2026-10" });
  });

  it("presentarLiquidacion: POST a /presentar", async () => {
    const fetchFn = fetchCon(respuestaJson(detalle({ estado: "presentada" })));
    const salida = await presentarLiquidacion(7, fetchFn);
    expect(salida.estado).toBe("presentada");
    const { url, init } = llamada(fetchFn);
    expect(url.endsWith("/liquidaciones/7/presentar")).toBe(true);
    expect(init.method).toBe("POST");
  });

  it("descartarLiquidacion: POST (no DELETE) y acepta 204 sin cuerpo", async () => {
    const fetchFn = fetchCon(new Response(null, { status: 204 }));
    await expect(descartarLiquidacion(7, fetchFn)).resolves.toBeUndefined();
    const { url, init } = llamada(fetchFn);
    expect(url.endsWith("/liquidaciones/7/descartar")).toBe(true);
    expect(init.method).toBe("POST");
  });

  it("cobrarLiquidacion: POST con el medio; no envia monto ni clave", async () => {
    const fetchFn = fetchCon(respuestaJson(detalle({ estado: "cobrada" })));
    await cobrarLiquidacion(7, "transferencia", fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(url.endsWith("/liquidaciones/7/cobrar")).toBe(true);
    expect(JSON.parse(String(init.body))).toEqual({ medio: "transferencia" });
  });

  it("revertirCobroLiquidacion: el motivo viaja solo en el cuerpo", async () => {
    const fetchFn = fetchCon(respuestaJson(detalle({ revertida: true })));
    await revertirCobroLiquidacion(7, "cobro duplicado", fetchFn);
    const { url, init } = llamada(fetchFn);
    expect(url.endsWith("/liquidaciones/7/revertir-cobro")).toBe(true);
    expect(url).not.toContain("duplicado");
    expect(JSON.parse(String(init.body))).toEqual({ motivo: "cobro duplicado" });
  });

  it("listarObrasSociales: GET del catalogo", async () => {
    const fetchFn = fetchCon(respuestaJson([obraSocial()]));
    expect((await listarObrasSociales(fetchFn))[0]?.nombre).toBe("OS Ficticia Demo");
    expect(llamada(fetchFn).url.endsWith("/obras-sociales")).toBe(true);
  });

  it("un error del servidor conserva el estado y el mensaje (409 caja pendiente)", async () => {
    const fallo = cobrarLiquidacion(7, "efectivo", fetchCon(respuestaJson({ detail: "hay una caja anterior sin cerrar" }, 409)));
    await expect(fallo).rejects.toMatchObject({ httpStatus: 409, message: "hay una caja anterior sin cerrar" });
  });

  it.each([
    ["total numerico", { ...liquidacion(), total: 10500 }],
    ["estado desconocido", { ...liquidacion(), estado: "anulada" }],
    ["sin obra social", { ...liquidacion(), obra_social: undefined }],
  ])("listarLiquidaciones con forma inesperada: %s", async (_nombre, fila) => {
    await expect(listarLiquidaciones(fetchCon(respuestaJson([fila])))).rejects.toMatchObject({
      message: expect.stringContaining("forma inesperada"),
    });
  });

  it.each([
    ["sin planes", { ...detalle(), planes: undefined }],
    ["monto de fila numerico", { ...detalle(), planes: [plan({ items: [{ ...item(), monto: 10 as unknown as string }] })] }],
    ["revision no booleana", { ...detalle(), planes: [plan({ items: [{ ...item(), revision: "si" as unknown as boolean }] })] }],
  ])("obtenerLiquidacion con forma inesperada: %s", async (_nombre, cuerpo) => {
    await expect(obtenerLiquidacion(7, fetchCon(respuestaJson(cuerpo)))).rejects.toBeInstanceOf(ApiError);
  });
});

describe("descargarInforme", () => {
  it("GET autenticado del adjunto y devuelve el Blob con un nombre de archivo", async () => {
    const fetchFn = fetchCon(new Response("a;b", { status: 200, headers: { "Content-Type": "text/csv" } }));
    const { blob, nombre } = await descargarInforme(7, "csv", fetchFn);
    expect(blob.size).toBe(3);
    expect(blob).toBeInstanceOf(Blob);
    expect(nombre).toBe("liquidacion-7.csv");
    expect(llamada(fetchFn).url.endsWith("/liquidaciones/7/export.csv")).toBe(true);
  });

  it("el PDF usa su propia ruta y extension", async () => {
    const fetchFn = fetchCon(new Response("%PDF-1.4", { status: 200, headers: { "Content-Type": "application/pdf" } }));
    const { nombre } = await descargarInforme(9, "pdf", fetchFn);
    expect(nombre).toBe("liquidacion-9.pdf");
    expect(llamada(fetchFn).url.endsWith("/liquidaciones/9/export.pdf")).toBe(true);
  });

  it("un 403 es un ApiError con el mensaje del servidor", async () => {
    const fallo = descargarInforme(7, "csv", fetchCon(respuestaJson({ detail: "sin permiso" }, 403)));
    await expect(fallo).rejects.toMatchObject({ httpStatus: 403, message: "sin permiso" });
  });
});

describe("periodo", () => {
  it.each(["2026-10", "2026-01", "2026-12"])("acepta %s", (texto) => {
    expect(esPeriodoValido(texto)).toBe(true);
  });

  it.each(["", "2026-13", "2026-00", "2026-1", "202610", "2026-10-01", "octubre", " 2026-10"])(
    "rechaza %j",
    (texto) => {
      expect(esPeriodoValido(texto)).toBe(false);
    },
  );

  it("periodoATexto corta el texto, sin pasar por Date", () => {
    expect(periodoATexto("2026-10-01")).toBe("10/2026");
    expect(periodoATexto("2026-01-01")).toBe("01/2026");
    expect(periodoATexto("octubre")).toBe("—");
  });
});
