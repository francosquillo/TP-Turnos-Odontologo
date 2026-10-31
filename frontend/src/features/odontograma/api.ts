/** API del odontograma C-08: siempre con `fetchConAuth`, tipada y sin `any`.
 *
 * El motivo de una baja o correccion viaja en el cuerpo, nunca en la URL, y
 * nada de lo clinico se escribe en consola (D-12).
 */
import { fetchConAuth } from "../../shared/api-client";
import {
  esObjeto,
  esTextoONulo,
  inesperada,
  pedir,
  type FetchAutenticado,
} from "../../shared/api-json";
import { CARAS } from "./tipos";
import type { Catalogo, DatosHallazgo, Hallazgo, Historia, Listado } from "./tipos";

export interface CambiosHistoria {
  antecedentes?: string | null;
  alergias?: string | null;
}

function esHistoria(valor: unknown): valor is Historia {
  if (!esObjeto(valor)) return false;
  return (
    typeof valor["id"] === "number" &&
    typeof valor["paciente_id"] === "number" &&
    esTextoONulo(valor["antecedentes"]) &&
    esTextoONulo(valor["alergias"]) &&
    typeof valor["updated_at"] === "string" &&
    esTextoONulo(valor["deleted_at"])
  );
}

function esHallazgo(valor: unknown): valor is Hallazgo {
  if (!esObjeto(valor)) return false;
  return (
    typeof valor["id"] === "number" &&
    typeof valor["hc_id"] === "number" &&
    typeof valor["pieza_fdi"] === "number" &&
    typeof valor["cara"] === "string" &&
    (CARAS as readonly string[]).includes(valor["cara"]) &&
    typeof valor["estado"] === "string" &&
    typeof valor["fecha"] === "string" &&
    esTextoONulo(valor["deleted_at"]) &&
    esTextoONulo(valor["motivo_baja"]) &&
    typeof valor["es_propio"] === "boolean"
  );
}

const ALCANCES: readonly string[] = ["cualquiera", "pieza"];

function esCatalogo(valor: unknown): valor is Catalogo {
  if (!esObjeto(valor) || typeof valor["version"] !== "number") return false;
  const estados = valor["estados"];
  return (
    Array.isArray(estados) &&
    estados.every(
      (e: unknown) =>
        esObjeto(e) &&
        typeof e["codigo"] === "string" &&
        typeof e["nombre"] === "string" &&
        typeof e["alcance"] === "string" &&
        ALCANCES.includes(e["alcance"]),
    )
  );
}

function hallazgoDe(respuesta: Response, datos: unknown): Hallazgo {
  if (!esObjeto(datos) || !esHallazgo(datos["hallazgo"])) throw inesperada(respuesta, "hallazgo");
  return datos["hallazgo"];
}

// --- Catalogo e historia -----------------------------------------------------

export async function obtenerCatalogo(fetchFn: FetchAutenticado = fetchConAuth): Promise<Catalogo> {
  const { respuesta, datos } = await pedir("/odontograma/catalogo", fetchFn);
  if (!esCatalogo(datos)) throw inesperada(respuesta, "catálogo");
  return datos;
}

/** Historia activa del paciente o `null` si todavia no tiene. */
export async function buscarHistoria(
  pacienteId: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Historia | null> {
  const { respuesta, datos } = await pedir(`/historias?paciente_id=${pacienteId}`, fetchFn);
  if (!Array.isArray(datos) || !datos.every(esHistoria)) throw inesperada(respuesta, "historia");
  return datos[0] ?? null;
}

export async function abrirHistoria(
  pacienteId: number,
  datos: CambiosHistoria,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Historia> {
  const { respuesta, datos: cuerpo } = await pedir("/historias", fetchFn, "POST", {
    paciente_id: pacienteId,
    ...datos,
  });
  if (!esHistoria(cuerpo)) throw inesperada(respuesta, "historia");
  return cuerpo;
}

export async function actualizarHistoria(
  id: number,
  cambios: CambiosHistoria,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Historia> {
  const { respuesta, datos } = await pedir(`/historias/${id}`, fetchFn, "PATCH", cambios);
  if (!esHistoria(datos)) throw inesperada(respuesta, "historia");
  return datos;
}

// --- Hallazgos ------------------------------------------------------------------

/** Todos los hallazgos de la historia, anulados incluidos (el historial se arma en pantalla). */
export async function listarHallazgos(
  hcId: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Listado> {
  const { respuesta, datos } = await pedir(
    `/odontograma/${hcId}/hallazgos?incluir_anulados=true`,
    fetchFn,
  );
  if (!esObjeto(datos)) throw inesperada(respuesta, "hallazgos");
  const alergias = datos["alergias"];
  const hallazgos = datos["hallazgos"];
  if (!esTextoONulo(alergias) || !Array.isArray(hallazgos) || !hallazgos.every(esHallazgo)) {
    throw inesperada(respuesta, "hallazgos");
  }
  return { alergias, hallazgos };
}

export async function registrarHallazgo(
  hcId: number,
  datos: DatosHallazgo,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Hallazgo> {
  const { respuesta, datos: cuerpo } = await pedir(`/odontograma/${hcId}/hallazgos`, fetchFn, "POST", datos);
  return hallazgoDe(respuesta, cuerpo);
}

/** Corrige un error: el servidor da de baja el original y devuelve la fila nueva. */
export async function corregirHallazgo(
  hcId: number,
  id: number,
  datos: DatosHallazgo,
  motivo: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Hallazgo> {
  const { respuesta, datos: cuerpo } = await pedir(
    `/odontograma/${hcId}/hallazgos/${id}`,
    fetchFn,
    "PUT",
    { ...datos, motivo },
  );
  return hallazgoDe(respuesta, cuerpo);
}

export async function darDeBajaHallazgo(
  hcId: number,
  id: number,
  motivoBaja: string,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<Hallazgo> {
  const { respuesta, datos } = await pedir(
    `/odontograma/${hcId}/hallazgos/${id}/baja`,
    fetchFn,
    "POST",
    { motivo_baja: motivoBaja },
  );
  return hallazgoDe(respuesta, datos);
}
