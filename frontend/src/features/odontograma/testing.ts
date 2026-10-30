/** Fixtures compartidas por los tests del odontograma (datos 100% ficticios). */
import type { Catalogo, Hallazgo, Historia } from "./tipos";

export const CATALOGO: Catalogo = {
  version: 1,
  estados: [
    { codigo: "sano", nombre: "Sano", alcance: "cualquiera" },
    { codigo: "caries", nombre: "Caries", alcance: "cualquiera" },
    { codigo: "obturacion", nombre: "Obturación", alcance: "cualquiera" },
    { codigo: "corona", nombre: "Corona", alcance: "pieza" },
    { codigo: "endodoncia", nombre: "Endodoncia", alcance: "pieza" },
    { codigo: "implante", nombre: "Implante", alcance: "pieza" },
    { codigo: "ausente", nombre: "Ausente", alcance: "pieza" },
  ],
};

export function historia(parcial: Partial<Historia> = {}): Historia {
  return {
    id: 7,
    paciente_id: 3,
    antecedentes: null,
    alergias: null,
    created_at: "2026-10-30T10:00:00Z",
    updated_at: "2026-10-30T10:00:00Z",
    deleted_at: null,
    motivo_baja: null,
    ...parcial,
  };
}

let secuencia = 100;

export function hallazgo(parcial: Partial<Hallazgo> = {}): Hallazgo {
  secuencia += 1;
  return {
    id: secuencia,
    hc_id: 7,
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

export function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
