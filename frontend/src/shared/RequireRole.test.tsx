import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProveedor } from "./auth-context";
import { limpiarAccess } from "./api-client";
import { RequireRole } from "./RequireRole";

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("RequireRole C-03", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    limpiarAccess();
  });

  it("secretaria en ruta admin ve 'sin permiso' (sesion restaurada via refresh)", async () => {
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      const destino = String(url);
      if (destino.includes("/auth/refresh")) {
        return Promise.resolve(
          respuestaJson({ access_token: "a", token_type: "bearer" }, 200),
        );
      }
      if (destino.includes("/auth/me")) {
        return Promise.resolve(
          respuestaJson(
            { id: 2, email: "secre@demo.test", nombre: "S", rol: "secretaria" },
            200,
          ),
        );
      }
      return Promise.resolve(respuestaJson({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <AuthProveedor>
        <RequireRole roles={["admin"]}>
          <p>contenido secreto</p>
        </RequireRole>
      </AuthProveedor>,
    );

    expect(await screen.findByText("sin permiso")).toBeDefined();
    expect(screen.queryByText("contenido secreto")).toBeNull();
  });
});
