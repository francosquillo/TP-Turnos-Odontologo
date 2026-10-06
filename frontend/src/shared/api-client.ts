/** Cliente API tipado (cero `any`): envuelve GET /health con errores tipados. */

export interface HealthStatus {
  status: "ok" | "degraded";
  postgres: "up" | "down";
  redis: "up" | "down";
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
