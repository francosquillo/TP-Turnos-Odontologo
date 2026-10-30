/** API lista de espera C-07: staff con `fetchConAuth`, pública sin Bearer. */
import { ApiError, apiUrl, fetchConAuth } from "../../shared/api-client";
import type { EntradaEspera, HuecoOferta, OfertaPublica } from "./tipos";

type FetchAutenticado = (input: string, init?: RequestInit) => Promise<Response>;

const ESTADOS = ["activa", "ofrecida", "convertida", "vencida"];

function esEntrada(valor: unknown): valor is EntradaEspera {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return (
    typeof v["id"] === "number" &&
    typeof v["created_at"] === "string" &&
    typeof v["estado"] === "string" &&
    ESTADOS.includes(v["estado"])
  );
}

function esOferta(valor: unknown): valor is OfertaPublica {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return (
    typeof v["nombre_pila"] === "string" &&
    typeof v["inicio"] === "string" &&
    typeof v["fin"] === "string" &&
    typeof v["oferta_expira_en"] === "string"
  );
}

async function leerJson(respuesta: Response): Promise<unknown> {
  try {
    return (await respuesta.json()) as unknown;
  } catch {
    return null;
  }
}

function detalleDe(cuerpo: unknown): string {
  if (typeof cuerpo === "object" && cuerpo !== null) {
    const detalle = (cuerpo as Record<string, unknown>)["detail"];
    if (typeof detalle === "string") return detalle;
  }
  return "";
}

async function errorDe(respuesta: Response): Promise<ApiError> {
  const detalle = detalleDe(await leerJson(respuesta));
  return new ApiError(respuesta.status, detalle || `La API respondió ${respuesta.status}`);
}

// --- Staff --------------------------------------------------------------

export async function listarEspera(fetchFn: FetchAutenticado = fetchConAuth): Promise<EntradaEspera[]> {
  const respuesta = await fetchFn(apiUrl("/lista-espera"));
  if (!respuesta.ok) throw await errorDe(respuesta);
  const cuerpo = await leerJson(respuesta);
  if (!Array.isArray(cuerpo) || !cuerpo.every(esEntrada)) {
    throw new ApiError(respuesta.status, "Respuesta de lista de espera inesperada");
  }
  return cuerpo;
}

async function postStaff(ruta: string, cuerpo: unknown, fetchFn: FetchAutenticado): Promise<void> {
  const respuesta = await fetchFn(apiUrl(ruta), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    ...(cuerpo === undefined ? {} : { body: JSON.stringify(cuerpo) }),
  });
  if (!respuesta.ok) throw await errorDe(respuesta);
}

export function ofrecerHueco(
  id: number,
  hueco: HuecoOferta,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<void> {
  return postStaff(`/lista-espera/${id}/ofrecer`, hueco, fetchFn);
}

export function convertirEntrada(id: number, fetchFn: FetchAutenticado = fetchConAuth): Promise<void> {
  return postStaff(`/lista-espera/${id}/convertir`, undefined, fetchFn);
}

export function darDeBaja(
  id: number,
  motivoBaja: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<void> {
  return postStaff(`/lista-espera/${id}/baja`, { motivo_baja: motivoBaja }, fetchFn);
}

// --- Pública (sin Bearer: el token es la auth) ----------------------------

export interface Alternativa {
  inicio: string;
  fin: string;
}

export type ResultadoPublico =
  | { tipo: "ok" }
  | { tipo: "no-existe" }
  | { tipo: "resuelta" }
  | { tipo: "vencida" }
  | { tipo: "hueco-ocupado"; alternativas: Alternativa[] }
  | { tipo: "error" };

function alternativasDe(cuerpo: unknown): Alternativa[] {
  if (typeof cuerpo !== "object" || cuerpo === null) return [];
  const lista = (cuerpo as Record<string, unknown>)["alternativas"];
  if (!Array.isArray(lista)) return [];
  return lista.filter(
    (a): a is Alternativa =>
      typeof a === "object" &&
      a !== null &&
      typeof (a as Record<string, unknown>)["inicio"] === "string" &&
      typeof (a as Record<string, unknown>)["fin"] === "string",
  );
}

export type ResultadoOferta =
  | { tipo: "ok"; oferta: OfertaPublica }
  | { tipo: "no-existe" }
  | { tipo: "no-disponible" }
  | { tipo: "error" };

export async function verOferta(token: string): Promise<ResultadoOferta> {
  try {
    const respuesta = await fetch(apiUrl(`/lista-espera/oferta/${encodeURIComponent(token)}`));
    if (respuesta.status === 404) return { tipo: "no-existe" };
    if (respuesta.status === 410) return { tipo: "no-disponible" };
    if (!respuesta.ok) return { tipo: "error" };
    const cuerpo = await leerJson(respuesta);
    return esOferta(cuerpo) ? { tipo: "ok", oferta: cuerpo } : { tipo: "error" };
  } catch {
    return { tipo: "error" };
  }
}

async function responderOferta(
  accion: "aceptar" | "rechazar",
  token: string,
): Promise<ResultadoPublico> {
  try {
    const respuesta = await fetch(apiUrl(`/lista-espera/${accion}/${encodeURIComponent(token)}`), {
      method: "POST",
    });
    if (respuesta.ok) return { tipo: "ok" };
    const cuerpo = await leerJson(respuesta);
    if (respuesta.status === 404) return { tipo: "no-existe" };
    if (respuesta.status === 409) {
      return { tipo: "hueco-ocupado", alternativas: alternativasDe(cuerpo) };
    }
    if (respuesta.status === 410) {
      return detalleDe(cuerpo) === "oferta expirada" ? { tipo: "vencida" } : { tipo: "resuelta" };
    }
    return { tipo: "error" };
  } catch {
    return { tipo: "error" };
  }
}

export const aceptarOferta = (token: string): Promise<ResultadoPublico> =>
  responderOferta("aceptar", token);
export const rechazarOferta = (token: string): Promise<ResultadoPublico> =>
  responderOferta("rechazar", token);
