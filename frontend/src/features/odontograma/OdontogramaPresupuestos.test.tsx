import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { presupuesto, TRATAMIENTOS } from "../presupuestos/testing";
import { OdontogramaPage } from "./OdontogramaPage";
import { CATALOGO, hallazgo, historia, respuestaJson } from "./testing";
import type { Hallazgo, Historia } from "./tipos";

interface Mundo {
  historias: Historia[];
  hallazgos: Hallazgo[];
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    if (ruta === "/odontograma/catalogo") return Promise.resolve(respuestaJson(CATALOGO));
    if (ruta.startsWith("/historias?paciente_id=")) return Promise.resolve(respuestaJson(mundo.historias));
    if (ruta.includes("/hallazgos?incluir_anulados=true")) {
      return Promise.resolve(respuestaJson({ alergias: null, hallazgos: mundo.hallazgos }));
    }
    if (ruta.startsWith("/presupuestos?paciente_id=")) {
      return Promise.resolve(respuestaJson([presupuesto({ id: 31, estado: "presentado", es_propio: false })]));
    }
    if (ruta === "/tratamientos") return Promise.resolve(respuestaJson(TRATAMIENTOS));
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function montar(rol: "odontologo" | "secretaria"): void {
  render(<OdontogramaPage pacienteId={3} pacienteNombre="Ana Ficticia" rol={rol} alVolver={vi.fn()} />);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("OdontogramaPage con presupuestos (C-09)", () => {
  it.each(["odontologo", "secretaria"] as const)("%s ve los presupuestos del paciente", async (rol) => {
    stubFetch({ historias: [historia()], hallazgos: [hallazgo({ id: 11 })] });
    montar(rol);
    const panel = await screen.findByRole("region", { name: "Presupuestos" });
    expect(panel).toBeTruthy();
    expect((await screen.findByRole("button", { name: /Presupuesto 31/ })).textContent).toContain("Presentado");
  });

  it("el odontologo puede armar uno nuevo y la secretaria no", async () => {
    stubFetch({ historias: [historia()], hallazgos: [hallazgo({ id: 11 })] });
    montar("odontologo");
    expect(await screen.findByRole("button", { name: "Nuevo presupuesto" })).toBeTruthy();
  });

  it("la secretaria no ve el boton de alta", async () => {
    stubFetch({ historias: [historia()], hallazgos: [hallazgo({ id: 11 })] });
    montar("secretaria");
    await screen.findByRole("button", { name: /Presupuesto 31/ });
    expect(screen.queryByRole("button", { name: "Nuevo presupuesto" })).toBeNull();
  });

  it("sin historia no se ofrece el panel ni se piden presupuestos", async () => {
    const fetchMock = stubFetch({ historias: [], hallazgos: [] });
    montar("odontologo");
    expect(await screen.findByRole("button", { name: "Abrir historia" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Presupuestos" })).toBeNull();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes("/presupuestos"))).toBe(false);
  });

  it("abrir un presupuesto no rompe el resto del odontograma", async () => {
    stubFetch({ historias: [historia()], hallazgos: [hallazgo({ id: 11 })] });
    montar("secretaria");
    await userEvent.click(await screen.findByRole("button", { name: /Presupuesto 31/ }));
    expect(screen.getByLabelText("Estado del presupuesto").textContent).toBe("Presentado");
    expect(screen.getAllByRole("group", { name: /Superior derecho/ }).length).toBeGreaterThan(0);
  });
});
