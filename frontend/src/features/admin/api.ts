/** API de usuarios admin C-12: siempre con `fetchConAuth`, tipada y sin `any`.
 *
 * La contraseña viaja solo en el cuerpo del alta y nunca se devuelve ni se escribe en consola.
 * Desactivar es `PATCH .../desactivar`; reactivar es `PATCH` con `activo: true`.
 */
import { apiUrl, fetchConAuth } from "../../shared/api-client";
import { errorDe, esObjeto, inesperada, pedir, type FetchAutenticado } from "../../shared/api-json";
import { esRol } from "./tipos";
import type { DatosAltaUsuario, Rol, UsuarioAdmin } from "./tipos";

function esUsuario(valor: unknown): valor is UsuarioAdmin {
  return (
    esObjeto(valor) &&
    typeof valor["id"] === "number" &&
    typeof valor["nombre"] === "string" &&
    typeof valor["email"] === "string" &&
    esRol(valor["rol"]) &&
    typeof valor["activo"] === "boolean"
  );
}

export async function listarUsuarios(fetchFn: FetchAutenticado = fetchConAuth): Promise<UsuarioAdmin[]> {
  const { respuesta, datos } = await pedir("/admin/usuarios", fetchFn);
  if (!Array.isArray(datos) || !datos.every(esUsuario)) throw inesperada(respuesta, "usuarios");
  return datos;
}

export async function crearUsuario(
  datos: DatosAltaUsuario,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<UsuarioAdmin> {
  const { respuesta, datos: cuerpo } = await pedir("/admin/usuarios", fetchFn, "POST", datos);
  if (!esUsuario(cuerpo)) throw inesperada(respuesta, "usuario");
  return cuerpo;
}

export async function cambiarRol(
  id: number,
  rol: Rol,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<UsuarioAdmin> {
  const { respuesta, datos } = await pedir(`/admin/usuarios/${id}`, fetchFn, "PATCH", { rol });
  if (!esUsuario(datos)) throw inesperada(respuesta, "usuario");
  return datos;
}

export async function desactivarUsuario(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<UsuarioAdmin> {
  const { respuesta, datos } = await pedir(`/admin/usuarios/${id}/desactivar`, fetchFn, "PATCH");
  if (!esUsuario(datos)) throw inesperada(respuesta, "usuario");
  return datos;
}

export async function reactivarUsuario(
  id: number,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<UsuarioAdmin> {
  const { respuesta, datos } = await pedir(`/admin/usuarios/${id}`, fetchFn, "PATCH", { activo: true });
  if (!esUsuario(datos)) throw inesperada(respuesta, "usuario");
  return datos;
}

export interface ArchivoDescargado {
  blob: Blob;
  nombre: string;
}

const NOMBRE_EXPORTACION = "export-total.zip";

function nombreDeDisposicion(cabecera: string | null): string {
  const coincide = cabecera === null ? null : /filename="([^"/\\]+)"/.exec(cabecera);
  return coincide?.[1] ?? NOMBRE_EXPORTACION;
}

export interface ErrorFilaImportacion {
  fila: number;
  motivo: string;
}

export interface ReporteImportacion {
  creados: number;
  rechazados: number;
  errores: ErrorFilaImportacion[];
}

const esErrorFila = (valor: unknown): valor is ErrorFilaImportacion =>
  esObjeto(valor) && typeof valor["fila"] === "number" && typeof valor["motivo"] === "string";

function esReporte(valor: unknown): valor is ReporteImportacion {
  return (
    esObjeto(valor) &&
    typeof valor["creados"] === "number" &&
    typeof valor["rechazados"] === "number" &&
    Array.isArray(valor["errores"]) &&
    valor["errores"].every(esErrorFila)
  );
}

/** Sube un CSV o XLSX de pacientes (multipart; el navegador fija el Content-Type con el limite). */
export async function importarPacientes(
  archivo: File,
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<ReporteImportacion> {
  const cuerpo = new FormData();
  cuerpo.append("archivo", archivo);
  const respuesta = await fetchFn(apiUrl("/pacientes/import"), { method: "POST", body: cuerpo });
  if (!respuesta.ok) throw await errorDe(respuesta);
  const datos = (await respuesta.json()) as unknown;
  if (!esReporte(datos)) throw inesperada(respuesta, "importación");
  return datos;
}

/** Descarga la exportacion total (solo admin) con la sesion autenticada, como `Blob`. */
export async function descargarExportacionTotal(
  fetchFn: FetchAutenticado = fetchConAuth,
): Promise<ArchivoDescargado> {
  const respuesta = await fetchFn(apiUrl("/admin/export-total"));
  if (!respuesta.ok) throw await errorDe(respuesta);
  return {
    blob: await respuesta.blob(),
    nombre: nombreDeDisposicion(respuesta.headers.get("Content-Disposition")),
  };
}
