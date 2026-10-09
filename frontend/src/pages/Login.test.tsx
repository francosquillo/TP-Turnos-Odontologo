import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProveedor } from "../shared/auth-context";
import { limpiarAccess } from "../shared/api-client";
import { Login } from "./Login";

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Login C-03", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    limpiarAccess();
  });

  it("401 generico muestra 'credenciales inválidas' sin enumerar", async () => {
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      if (String(url).includes("/auth/login")) {
        return Promise.resolve(
          respuestaJson({ detail: "credenciales inválidas" }, 401),
        );
      }
      return Promise.resolve(respuestaJson({}, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    const usuario = userEvent.setup();
    render(
      <AuthProveedor>
        <Login />
      </AuthProveedor>,
    );

    await usuario.type(screen.getByLabelText(/email/i), "nadie@demo.test");
    await usuario.type(screen.getByLabelText(/contraseña/i), "mala-999");
    await usuario.click(screen.getByRole("button", { name: /ingresar/i }));

    expect(await screen.findByText("credenciales inválidas")).toBeDefined();
    expect(screen.queryByText(/no registrado/i)).toBeNull();
  });
});
