/** API agenda C-04 sobre `fetchConAuth` (C-03): tipado, cero `any`. */
import { ApiError, apiUrl, fetchConAuth } from "../../shared/api-client";
import type { Hueco, TurnoAgenda, VistaAgenda } from "./tipos";

export class ConflictoHuecoError extends Error {
  readonly alternativas: Hueco[];

  constructor(alternativas: Hueco[]) {
    super("hueco ocupado");
    this.name = "ConflictoHuecoError";
    this.alternativas = alternativas;
  }
}

type FetchAutenticado = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

function esTurno(valor: unknown): valor is TurnoAgenda {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return (
    typeof v["id"] === "number" &&
    typeof v["inicio"] === "string" &&
    typeof v["fin"] === "string" &&
    typeof v["estado"] === "string"
  );
}

function esHueco(valor: unknown): valor is Hueco {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return typeof v["inicio"] === "string" && typeof v["fin"] === "string";
}

async function leerJson(respuesta: Response): Promise<unknown> {
  try {
    return (await respuesta.json()) as unknown;
  } catch {
    return null;
  }
}

export async function listarAgenda(
  vista: VistaAgenda,
  fecha: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<TurnoAgenda[]> {
  const respuesta = await fetchFn(
    apiUrl(`/agenda?vista=${vista}&fecha=${fecha}`),
  );
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status}`);
  }
  const cuerpo: unknown = await leerJson(respuesta);
  if (!Array.isArray(cuerpo) || !cuerpo.every(esTurno)) {
    throw new ApiError(respuesta.status, "Respuesta de agenda inesperada");
  }
  return cuerpo;
}

export interface CrearTurnoDatos {
  paciente_id: number;
  profesional_id: number;
  sillon_id: number;
  inicio: string;
  fin: string;
}

export async function crearTurno(
  datos: CrearTurnoDatos,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<TurnoAgenda> {
  const respuesta = await fetchFn(apiUrl("/turnos"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  if (respuesta.status === 409) {
    const cuerpo = (await leerJson(respuesta)) as {
      alternativas?: unknown;
    } | null;
    const alts = Array.isArray(cuerpo?.alternativas)
      ? (cuerpo?.alternativas as unknown[]).filter(esHueco)
      : [];
    throw new ConflictoHuecoError(alts);
  }
  if (!respuesta.ok || respuesta.status !== 201) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status}`);
  }
  const cuerpo: unknown = await leerJson(respuesta);
  if (!esTurno(cuerpo)) {
    throw new ApiError(respuesta.status, "Respuesta de turno inesperada");
  }
  return cuerpo;
}

export async function cambiarEstadoTurno(
  id: number,
  estado: string,
  motivo: string | null,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<TurnoAgenda> {
  const respuesta = await fetchFn(apiUrl(`/turnos/${id}/estado`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(motivo === null ? { estado } : { estado, motivo }),
  });
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status}`);
  }
  const cuerpo: unknown = await leerJson(respuesta);
  if (!esTurno(cuerpo)) {
    throw new ApiError(respuesta.status, "Respuesta de turno inesperada");
  }
  return cuerpo;
}

export async function reprogramarTurno(
  id: number,
  inicio: string,
  fin: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<TurnoAgenda> {
  const respuesta = await fetchFn(apiUrl(`/turnos/${id}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inicio, fin }),
  });
  if (respuesta.status === 409) {
    const cuerpo = (await leerJson(respuesta)) as {
      alternativas?: unknown;
    } | null;
    const alts = Array.isArray(cuerpo?.alternativas)
      ? (cuerpo?.alternativas as unknown[]).filter(esHueco)
      : [];
    throw new ConflictoHuecoError(alts);
  }
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status}`);
  }
  const cuerpo: unknown = await leerJson(respuesta);
  if (!esTurno(cuerpo)) {
    throw new ApiError(respuesta.status, "Respuesta de turno inesperada");
  }
  return cuerpo;
}
