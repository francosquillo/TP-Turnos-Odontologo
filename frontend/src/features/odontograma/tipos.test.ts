import { describe, expect, it } from "vitest";
import {
  CUADRANTES,
  carasPermitidas,
  estadoVigente,
  etiquetaCara,
  todasLasPiezas,
} from "./tipos";
import type { Hallazgo } from "./tipos";

let secuencia = 0;
function hallazgo(parcial: Partial<Hallazgo>): Hallazgo {
  secuencia += 1;
  return {
    id: secuencia,
    hc_id: 1,
    pieza_fdi: 16,
    cara: "oclusal",
    estado: "caries",
    catalogo_version: 1,
    fecha: "2026-10-10T10:00:00Z",
    profesional_id: 1,
    corrige_a_id: null,
    deleted_at: null,
    motivo_baja: null,
    es_propio: true,
    ...parcial,
  };
}

describe("grilla FDI", () => {
  it("respeta el orden clinico de cada cuadrante", () => {
    const porNombre = Object.fromEntries(CUADRANTES.map((c) => [c.id, c.piezas]));
    expect(porNombre["sup-der"]).toEqual([18, 17, 16, 15, 14, 13, 12, 11]);
    expect(porNombre["sup-izq"]).toEqual([21, 22, 23, 24, 25, 26, 27, 28]);
    expect(porNombre["inf-der"]).toEqual([48, 47, 46, 45, 44, 43, 42, 41]);
    expect(porNombre["inf-izq"]).toEqual([31, 32, 33, 34, 35, 36, 37, 38]);
  });

  it("tiene 32 piezas y ninguna de las inexistentes 19, 20, 29, 30, 39, 40", () => {
    const piezas = todasLasPiezas();
    expect(piezas).toHaveLength(32);
    expect(new Set(piezas).size).toBe(32);
    for (const invalida of [19, 20, 29, 30, 39, 40]) {
      expect(piezas).not.toContain(invalida);
    }
  });
});

describe("carasPermitidas", () => {
  it("deja afuera palatina en inferiores y lingual en superiores", () => {
    expect(carasPermitidas(36, "cualquiera")).not.toContain("palatina");
    expect(carasPermitidas(36, "cualquiera")).toContain("lingual");
    expect(carasPermitidas(16, "cualquiera")).toContain("palatina");
    expect(carasPermitidas(16, "cualquiera")).not.toContain("lingual");
  });

  it("un estado de alcance pieza (ausente) solo admite pieza_completa", () => {
    expect(carasPermitidas(16, "pieza")).toEqual(["pieza_completa"]);
    expect(carasPermitidas(46, "pieza")).toEqual(["pieza_completa"]);
  });

  it("un estado de cualquier alcance incluye pieza_completa, oclusal y raiz", () => {
    const caras = carasPermitidas(26, "cualquiera");
    expect(caras).toEqual(expect.arrayContaining(["pieza_completa", "oclusal", "raiz", "mesial", "distal", "vestibular"]));
  });
});

describe("etiquetaCara", () => {
  it("rotula Incisal en incisivos y caninos y Oclusal en el resto", () => {
    expect(etiquetaCara(11, "oclusal")).toBe("Incisal");
    expect(etiquetaCara(43, "oclusal")).toBe("Incisal");
    expect(etiquetaCara(14, "oclusal")).toBe("Oclusal");
    expect(etiquetaCara(36, "oclusal")).toBe("Oclusal");
    expect(etiquetaCara(11, "mesial")).toBe("Mesial");
    expect(etiquetaCara(16, "pieza_completa")).toBe("Pieza completa");
  });
});

describe("estadoVigente", () => {
  it("toma el hallazgo mas reciente de cada cara e ignora los dados de baja", () => {
    const vigente = estadoVigente([
      hallazgo({ estado: "caries", fecha: "2026-10-01T10:00:00Z" }),
      hallazgo({ estado: "obturacion", fecha: "2026-10-20T10:00:00Z" }),
      hallazgo({ estado: "sano", fecha: "2026-10-25T10:00:00Z", deleted_at: "2026-10-26T10:00:00Z", motivo_baja: "error" }),
    ]);
    expect(vigente.get("oclusal")?.estado).toBe("obturacion");
    expect(vigente.size).toBe(1);
  });

  it("desempata por id cuando la fecha coincide", () => {
    const vigente = estadoVigente([
      hallazgo({ id: 50, estado: "caries" }),
      hallazgo({ id: 51, estado: "sano" }),
    ]);
    expect(vigente.get("oclusal")?.estado).toBe("sano");
  });

  it("una pieza_completa reciente tapa las caras antiguas", () => {
    const vigente = estadoVigente([
      hallazgo({ cara: "oclusal", estado: "caries", fecha: "2026-10-01T10:00:00Z" }),
      hallazgo({ cara: "mesial", estado: "caries", fecha: "2026-10-02T10:00:00Z" }),
      hallazgo({ cara: "pieza_completa", estado: "ausente", fecha: "2026-10-20T10:00:00Z" }),
    ]);
    expect(vigente.get("pieza_completa")?.estado).toBe("ausente");
    expect(vigente.has("oclusal")).toBe(false);
    expect(vigente.has("mesial")).toBe(false);
  });

  it("una cara reciente prevalece sobre una pieza_completa antigua", () => {
    const vigente = estadoVigente([
      hallazgo({ cara: "pieza_completa", estado: "corona", fecha: "2026-10-01T10:00:00Z" }),
      hallazgo({ cara: "oclusal", estado: "caries", fecha: "2026-10-20T10:00:00Z" }),
    ]);
    expect(vigente.get("oclusal")?.estado).toBe("caries");
    expect(vigente.get("pieza_completa")?.estado).toBe("corona");
  });

  it("sin hallazgos activos no hay estado", () => {
    expect(estadoVigente([]).size).toBe(0);
    expect(estadoVigente([hallazgo({ deleted_at: "2026-10-02T10:00:00Z", motivo_baja: "x" })]).size).toBe(0);
  });
});
