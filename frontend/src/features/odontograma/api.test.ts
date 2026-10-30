import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import {
  abrirHistoria,
  actualizarHistoria,
  buscarHistoria,
  corregirHallazgo,
  darDeBajaHallazgo,
  listarHallazgos,
  obtenerCatalogo,
  registrarHallazgo,
} from "./api";

const HC = {
  id: 7,
  paciente_id: 3,
  antecedentes: null,
  alergias: "Penicilina",
  created_at: "2026-10-30T10:00:00Z",
  updated_at: "2026-10-30T10:00:00Z",
  deleted_at: null,
  motivo_baja: null,
};

const HALLAZGO = {
  id: 11,
  hc_id: 7,
  pieza_fdi: 16,
  cara: "oclusal",
  estado: "caries",
  catalogo_version: 1,
  fecha: "2026-10-30T10:00:00Z",
  profesional_id: 1,
  corrige_a_id: null,
  deleted_at: null,
  motivo_baja: null,
  es_propio: true,
};

function json(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api odontograma", () => {
  it("busca la historia por paciente: devuelve la fila o null si la lista viene vacia", async () => {
    const fetchFn = vi.fn().mockResolvedValueOnce(json([HC])).mockResolvedValueOnce(json([]));
    expect((await buscarHistoria(3, fetchFn))?.id).toBe(7);
    expect(await buscarHistoria(4, fetchFn)).toBeNull();
    expect(String(fetchFn.mock.calls[0]?.[0])).toMatch(/\/historias\?paciente_id=3$/);
  });

  it("abre la historia con POST y cuerpo JSON sin campos de mas", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json(HC, 201));
    const hc = await abrirHistoria(3, { antecedentes: null, alergias: "Penicilina" }, fetchFn);
    expect(hc.alergias).toBe("Penicilina");
    const init = fetchFn.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      paciente_id: 3,
      antecedentes: null,
      alergias: "Penicilina",
    });
  });

  it("actualiza solo lo enviado con PATCH", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ ...HC, alergias: null }));
    await actualizarHistoria(7, { alergias: null }, fetchFn);
    const init = fetchFn.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(String(init.body))).toEqual({ alergias: null });
  });

  it("lista hallazgos con anulados y valida alergias en la raiz", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ alergias: null, hallazgos: [HALLAZGO] }));
    const listado = await listarHallazgos(7, fetchFn);
    expect(listado.alergias).toBeNull();
    expect(listado.hallazgos[0]?.es_propio).toBe(true);
    expect(String(fetchFn.mock.calls[0]?.[0])).toMatch(/\/odontograma\/7\/hallazgos\?incluir_anulados=true$/);
  });

  it("registra un hallazgo y devuelve el hallazgo (sin enviar autor, fecha ni version)", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ alergias: null, hallazgo: HALLAZGO }, 201));
    const creado = await registrarHallazgo(7, { pieza_fdi: 16, cara: "oclusal", estado: "caries" }, fetchFn);
    expect(creado.id).toBe(11);
    const init = fetchFn.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({ pieza_fdi: 16, cara: "oclusal", estado: "caries" });
  });

  it("corrige con PUT y entrega la fila nueva con id distinto", async () => {
    const nuevo = { ...HALLAZGO, id: 12, corrige_a_id: 11 };
    const fetchFn = vi.fn().mockResolvedValue(json({ alergias: null, hallazgo: nuevo }));
    const corregido = await corregirHallazgo(
      7,
      11,
      { pieza_fdi: 16, cara: "mesial", estado: "caries" },
      "pieza equivocada",
      fetchFn,
    );
    expect(corregido.id).toBe(12);
    expect(corregido.corrige_a_id).toBe(11);
    const init = fetchFn.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toMatchObject({ motivo: "pieza equivocada", cara: "mesial" });
  });

  it("da de baja un hallazgo con motivo en el cuerpo", async () => {
    const baja = { ...HALLAZGO, deleted_at: "2026-10-31T10:00:00Z", motivo_baja: "error" };
    const fetchFn = vi.fn().mockResolvedValue(json({ alergias: null, hallazgo: baja }));
    expect((await darDeBajaHallazgo(7, 11, "error", fetchFn)).motivo_baja).toBe("error");
    const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit];
    expect(url).not.toContain("error");
    expect(JSON.parse(String(init.body))).toEqual({ motivo_baja: "error" });
  });

  it("lee el catalogo vigente", async () => {
    const fetchFn = vi.fn().mockResolvedValue(
      json({ version: 1, estados: [{ codigo: "caries", nombre: "Caries", alcance: "cualquiera" }] }),
    );
    const catalogo = await obtenerCatalogo(fetchFn);
    expect(catalogo.estados[0]?.alcance).toBe("cualquiera");
  });

  it.each([
    [403, { detail: "solo el autor puede modificar el hallazgo" }, "solo el autor puede modificar el hallazgo"],
    [409, { detail: "el hallazgo ya está dado de baja" }, "el hallazgo ya está dado de baja"],
    [422, { detail: [{ loc: ["body", "pieza_fdi"], msg: "mal" }] }, "Datos inválidos"],
  ])("traduce %i a ApiError con el detalle legible", async (status, cuerpo, mensaje) => {
    const fetchFn = vi.fn().mockResolvedValue(json(cuerpo, status));
    const error = await registrarHallazgo(7, { pieza_fdi: 16, cara: "oclusal", estado: "caries" }, fetchFn).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).httpStatus).toBe(status);
    expect((error as ApiError).message).toBe(mensaje);
  });

  it("rechaza una respuesta con forma inesperada", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ alergias: null, hallazgos: [{ id: "x" }] }));
    await expect(listarHallazgos(7, fetchFn)).rejects.toBeInstanceOf(ApiError);
    const otra = vi.fn().mockResolvedValue(json({ foo: 1 }));
    await expect(obtenerCatalogo(otra)).rejects.toBeInstanceOf(ApiError);
    const tercera = vi.fn().mockResolvedValue(json({ id: 1 }));
    await expect(buscarHistoria(3, tercera)).rejects.toBeInstanceOf(ApiError);
  });
});
