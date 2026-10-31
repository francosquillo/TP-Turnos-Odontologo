/** Helpers JSON compartidos por los clientes de API de cada feature (C-09, D-21).
 *
 * Extraidos de `odontograma/api.ts` para no duplicarlos en presupuestos y cuenta
 * corriente. Los motivos y datos del paciente viajan en el cuerpo, nunca en la URL,
 * y aca no se escribe nada en consola (los datos pueden ser sensibles).
 */
import { ApiError, apiUrl } from "./api-client";

export type FetchAutenticado = (input: string, init?: RequestInit) => Promise<Response>;

export type MetodoHttp = "GET" | "POST" | "PUT" | "PATCH";

export const esObjeto = (valor: unknown): valor is Record<string, unknown> =>
  typeof valor === "object" && valor !== null;

export const esTextoONulo = (valor: unknown): valor is string | null =>
  valor === null || typeof valor === "string";

export async function leerJson(respuesta: Response): Promise<unknown> {
  try {
    return (await respuesta.json()) as unknown;
  } catch {
    return null;
  }
}

/** Mensaje legible: `detail` de texto tal cual; la lista de FastAPI (422) se resume. */
export function detalleDe(cuerpo: unknown): string {
  if (esObjeto(cuerpo)) {
    const detalle = cuerpo["detail"];
    if (typeof detalle === "string") return detalle;
    if (Array.isArray(detalle)) return "Datos inválidos";
  }
  return "";
}

export async function errorDe(respuesta: Response): Promise<ApiError> {
  const detalle = detalleDe(await leerJson(respuesta));
  return new ApiError(respuesta.status, detalle || `La API respondió ${respuesta.status}`);
}

export async function pedir(
  ruta: string,
  fetchFn: FetchAutenticado,
  metodo: MetodoHttp = "GET",
  cuerpo?: unknown,
): Promise<{ respuesta: Response; datos: unknown }> {
  const init: RequestInit =
    metodo === "GET"
      ? {}
      : { method: metodo, headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) };
  const respuesta = await fetchFn(apiUrl(ruta), init);
  if (!respuesta.ok) throw await errorDe(respuesta);
  return { respuesta, datos: await leerJson(respuesta) };
}

export function inesperada(respuesta: Response, que: string): ApiError {
  return new ApiError(respuesta.status, `Respuesta de ${que} con forma inesperada`);
}
