import { describe, expect, it, vi } from "vitest";
import { ApiError } from "./api-client";
import { detalleDe, errorDe, esObjeto, esTextoONulo, inesperada, leerJson, pedir } from "./api-json";

function json(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api-json", () => {
  it("detalleDe: texto tal cual, lista de validacion resumida, otra forma vacia", () => {
    expect(detalleDe({ detail: "el hallazgo cambió" })).toBe("el hallazgo cambió");
    expect(detalleDe({ detail: [{ msg: "x", input: "dato sensible" }] })).toBe("Datos inválidos");
    expect(detalleDe({})).toBe("");
    expect(detalleDe(null)).toBe("");
    expect(detalleDe("texto")).toBe("");
  });

  it("leerJson devuelve null si el cuerpo no es JSON", async () => {
    expect(await leerJson(new Response("no es json", { status: 500 }))).toBeNull();
    expect(await leerJson(json({ a: 1 }))).toEqual({ a: 1 });
  });

  it("errorDe usa el detail y, sin el, el codigo HTTP", async () => {
    const conDetalle = await errorDe(json({ detail: "ya existe" }, 409));
    expect(conDetalle).toBeInstanceOf(ApiError);
    expect([conDetalle.httpStatus, conDetalle.message]).toEqual([409, "ya existe"]);
    const sinDetalle = await errorDe(new Response("", { status: 503 }));
    expect([sinDetalle.httpStatus, sinDetalle.message]).toEqual([503, "La API respondió 503"]);
  });

  it("pedir GET: sin cuerpo ni cabeceras extra", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json([{ id: 1 }]));
    const { datos } = await pedir("/cosas", fetchFn);
    expect(datos).toEqual([{ id: 1 }]);
    const [url, init] = fetchFn.mock.calls[0] as [string, RequestInit];
    expect(url.endsWith("/cosas")).toBe(true);
    expect(init).toEqual({});
  });

  it("pedir POST/PUT/PATCH: el cuerpo viaja como JSON (nunca en la URL)", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ ok: true }, 201));
    for (const metodo of ["POST", "PUT", "PATCH"] as const) {
      await pedir("/cosas/1", fetchFn, metodo, { motivo: "texto privado" });
    }
    for (const [url, init] of fetchFn.mock.calls as [string, RequestInit][]) {
      expect(url).not.toContain("texto");
      expect(init.body).toBe(JSON.stringify({ motivo: "texto privado" }));
      expect(init.headers).toEqual({ "Content-Type": "application/json" });
    }
    expect((fetchFn.mock.calls.map((c) => (c[1] as RequestInit).method))).toEqual(["POST", "PUT", "PATCH"]);
  });

  it("pedir lanza ApiError con el mensaje del servidor ante un estado de error", async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ detail: "un hallazgo cambió" }, 409));
    await expect(pedir("/x", fetchFn, "POST", {})).rejects.toMatchObject({
      httpStatus: 409,
      message: "un hallazgo cambió",
    });
  });

  it("guardas y error de forma inesperada", () => {
    expect(esObjeto({})).toBe(true);
    expect(esObjeto(null)).toBe(false);
    expect(esObjeto("x")).toBe(false);
    expect(esTextoONulo(null)).toBe(true);
    expect(esTextoONulo("a")).toBe(true);
    expect(esTextoONulo(3)).toBe(false);
    const error = inesperada(new Response("", { status: 200 }), "cuenta");
    expect(error.message).toBe("Respuesta de cuenta con forma inesperada");
  });
});
