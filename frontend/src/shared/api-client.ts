/** Cliente API tipado (cero `any`): salud + sesion JWT (C-03, D-07).
 *
 * El access vive SOLO en memoria (nunca localStorage/sessionStorage);
 * el refresh viaja en cookie httpOnly con `credentials: "include"`.
 */

export type Rol = "admin" | "odontologo" | "secretaria";

export interface HealthStatus {
  status: "ok" | "degraded";
  postgres: "up" | "down";
  redis: "up" | "down";
}

export interface TokenRespuesta {
  access_token: string;
  token_type: string;
}

export interface MeRespuesta {
  id: number;
  email: string;
  nombre: string;
  rol: Rol;
}

export interface HooksAuth {
  alSesionExpirada?: () => void;
}

export class ApiError extends Error {
  readonly httpStatus: number;

  constructor(httpStatus: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.httpStatus = httpStatus;
  }
}

const BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function apiUrl(ruta: string): string {
  return `${BASE_URL}${ruta}`;
}

function esHealthStatus(valor: unknown): valor is HealthStatus {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return (
    (v["status"] === "ok" || v["status"] === "degraded") &&
    (v["postgres"] === "up" || v["postgres"] === "down") &&
    (v["redis"] === "up" || v["redis"] === "down")
  );
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE_URL}/health`, { signal });
  } catch (error) {
    throw new ApiError(0, `Sin conexión con la API: ${String(error)}`);
  }
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status}`);
  }
  const cuerpo: unknown = await respuesta.json();
  if (!esHealthStatus(cuerpo)) {
    throw new ApiError(respuesta.status, "Respuesta de salud con forma inesperada");
  }
  return cuerpo;
}

// --- Sesion (C-03, D-07): access solo en memoria ---------------------------

let accessEnMemoria: string | null = null;

export function definirAccess(token: string): void {
  accessEnMemoria = token;
}

export function limpiarAccess(): void {
  accessEnMemoria = null;
}

export function obtenerAccess(): string | null {
  return accessEnMemoria;
}

function esTokenRespuesta(valor: unknown): valor is TokenRespuesta {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return typeof v["access_token"] === "string" && typeof v["token_type"] === "string";
}

function esMeRespuesta(valor: unknown): valor is MeRespuesta {
  if (typeof valor !== "object" || valor === null) return false;
  const v = valor as Record<string, unknown>;
  return (
    typeof v["id"] === "number" &&
    typeof v["email"] === "string" &&
    typeof v["nombre"] === "string" &&
    (v["rol"] === "admin" || v["rol"] === "odontologo" || v["rol"] === "secretaria")
  );
}

export async function loginApi(email: string, password: string): Promise<MeRespuesta> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
  } catch (error) {
    throw new ApiError(0, `Sin conexión con la API: ${String(error)}`);
  }
  if (respuesta.status === 401) {
    throw new ApiError(401, "credenciales inválidas");
  }
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status}`);
  }
  const cuerpo: unknown = await respuesta.json();
  if (!esTokenRespuesta(cuerpo)) {
    throw new ApiError(respuesta.status, "Respuesta de login con forma inesperada");
  }
  definirAccess(cuerpo.access_token);
  return meApi(cuerpo.access_token);
}

export async function refreshApi(): Promise<string | null> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    return null;
  }
  if (!respuesta.ok) return null;
  const cuerpo: unknown = await respuesta.json();
  if (!esTokenRespuesta(cuerpo)) return null;
  definirAccess(cuerpo.access_token);
  return cuerpo.access_token;
}

export async function meApi(access: string): Promise<MeRespuesta> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${access}` },
      credentials: "include",
    });
  } catch (error) {
    throw new ApiError(0, `Sin conexión con la API: ${String(error)}`);
  }
  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status}`);
  }
  const cuerpo: unknown = await respuesta.json();
  if (!esMeRespuesta(cuerpo)) {
    throw new ApiError(respuesta.status, "Respuesta de sesión con forma inesperada");
  }
  return cuerpo;
}

export async function logoutApi(): Promise<void> {
  try {
    await fetch(`${BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    // Logout es best-effort: la sesion local se limpia igual.
  } finally {
    limpiarAccess();
  }
}

function conBearer(init: RequestInit | undefined, access: string): RequestInit {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${access}`);
  return { ...init, headers, credentials: "include" };
}

export async function fetchConAuth(
  input: string,
  init?: RequestInit,
  hooks?: HooksAuth,
): Promise<Response> {
  const access = obtenerAccess();
  const primera = await fetch(input, access === null ? { ...init, credentials: "include" } : conBearer(init, access));
  if (primera.status !== 401) return primera;
  // Un solo reintento silencioso via refresh (D-07); si falla, a login.
  const renovado = await refreshApi();
  if (renovado === null) {
    limpiarAccess();
    hooks?.alSesionExpirada?.();
    return primera;
  }
  const segunda = await fetch(input, conBearer(init, renovado));
  if (segunda.status === 401) {
    limpiarAccess();
    hooks?.alSesionExpirada?.();
  }
  return segunda;
}
