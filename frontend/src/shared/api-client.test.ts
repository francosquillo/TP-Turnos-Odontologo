import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  definirAccess,
  fetchConAuth,
  limpiarAccess,
  obtenerAccess,
} from "./api-client";

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("fetchConAuth C-03", () => {
  beforeEach(() => {
    limpiarAccess();
    vi.restoreAllMocks();
  });

  it("ante 401 renueva el par una vez y reintenta la llamada original", async () => {
    definirAccess("access-viejo");
    const fetchMock = vi.fn();
    fetchMock.mockImplementation((url: unknown, init?: RequestInit) => {
      const destino = String(url);
      if (destino.includes("/auth/refresh")) {
        return Promise.resolve(
          respuestaJson({ access_token: "access-nuevo", token_type: "bearer" }, 200),
        );
      }
      const auth = new Headers(init?.headers).get("Authorization");
      if (auth === "Bearer access-nuevo") {
        return Promise.resolve(respuestaJson({ id: 1 }, 200));
      }
      return Promise.resolve(respuestaJson({ detail: "x" }, 401));
    });
    vi.stubGlobal("fetch", fetchMock);

    const alSesionExpirada = vi.fn();
    const resp = await fetchConAuth("http://localhost:8000/admin/usuarios", {}, {
      alSesionExpirada,
    });

    expect(resp.status).toBe(200);
    expect(obtenerAccess()).toBe("access-nuevo");
    expect(alSesionExpirada).not.toHaveBeenCalled();
    const llamadasRefresh = fetchMock.mock.calls.filter((c) =>
      String(c[0]).includes("/auth/refresh"),
    );
    expect(llamadasRefresh).toHaveLength(1);
    expect(llamadasRefresh[0][1]).toMatchObject({ credentials: "include" });
  });

  it("si el refresh falla limpia la sesion y avisa con sesion nula", async () => {
    definirAccess("access-viejo");
    const fetchMock = vi.fn();
    fetchMock.mockImplementation((url: unknown) => {
      if (String(url).includes("/auth/refresh")) {
        return Promise.resolve(respuestaJson({ detail: "credenciales inválidas" }, 401));
      }
      return Promise.resolve(respuestaJson({ detail: "x" }, 401));
    });
    vi.stubGlobal("fetch", fetchMock);

    const alSesionExpirada = vi.fn();
    const resp = await fetchConAuth("http://localhost:8000/admin/usuarios", {}, {
      alSesionExpirada,
    });

    expect(resp.status).toBe(401);
    expect(obtenerAccess()).toBeNull();
    expect(alSesionExpirada).toHaveBeenCalledTimes(1);
  });
});
