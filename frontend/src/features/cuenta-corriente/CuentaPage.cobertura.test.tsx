import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CuentaPage } from "./CuentaPage";
import { cuenta, respuestaJson } from "./testing";

function stubFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    if (ruta === "/cuentas/3") return Promise.resolve(respuestaJson(cuenta()));
    if (ruta === "/pacientes/3/plan") {
      return Promise.resolve(respuestaJson({
        paciente_id: 3, plan_id: 1, plan_nombre: "Plan Base", obra_social_id: 1, obra_social_nombre: "OS Ficticia Demo",
      }));
    }
    if (ruta === "/planes" || ruta === "/tratamientos") return Promise.resolve(respuestaJson([]));
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CuentaPage con el panel de cobertura (C-11)", () => {
  it.each(["secretaria", "admin"] as const)("%s ve el plan del paciente dentro de la cuenta", async (rol) => {
    const fetchMock = stubFetch();
    render(<CuentaPage pacienteId={3} pacienteNombre="Ana Ficticia" rol={rol} alVolver={vi.fn()} />);
    expect((await screen.findByText(/Plan actual: Plan Base/)).textContent).toContain("OS Ficticia Demo");
    expect(screen.getByRole("heading", { name: "Cobertura de obra social" })).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/pacientes/3/plan"))).toBe(true);
  });
});
