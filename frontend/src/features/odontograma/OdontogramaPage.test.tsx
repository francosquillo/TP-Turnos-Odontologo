import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AlergiasAviso } from "./AlergiasAviso";
import { OdontogramaPage } from "./OdontogramaPage";
import { CATALOGO, hallazgo, historia, respuestaJson } from "./testing";
import type { Hallazgo, Historia } from "./tipos";

interface Mundo {
  historias: Historia[];
  hallazgos: Hallazgo[];
}

/** fetch falso que responde a las rutas del feature y registra cada pedido. */
function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    if (ruta === "/odontograma/catalogo") return Promise.resolve(respuestaJson(CATALOGO));
    if (ruta.startsWith("/historias?paciente_id=")) return Promise.resolve(respuestaJson(mundo.historias));
    if (ruta === "/historias" && metodo === "POST") {
      const nueva = historia({ id: 7, alergias: null });
      mundo.historias = [nueva];
      return Promise.resolve(respuestaJson(nueva, 201));
    }
    if (/^\/historias\/\d+$/.test(ruta) && metodo === "PATCH") {
      const cambios = JSON.parse(String(init?.body)) as Partial<Historia>;
      const actualizada = { ...(mundo.historias[0] as Historia), ...cambios };
      mundo.historias = [actualizada];
      return Promise.resolve(respuestaJson(actualizada));
    }
    if (ruta.includes("/hallazgos?incluir_anulados=true")) {
      return Promise.resolve(
        respuestaJson({ alergias: mundo.historias[0]?.alergias ?? null, hallazgos: mundo.hallazgos }),
      );
    }
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function montar(rol: "odontologo" | "secretaria" = "odontologo"): void {
  render(<OdontogramaPage pacienteId={3} pacienteNombre="Ana Ficticia" rol={rol} alVolver={vi.fn()} />);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AlergiasAviso", () => {
  it("muestra el texto de las alergias con una etiqueta, no solo color", () => {
    render(<AlergiasAviso alergias="Penicilina y látex" />);
    const aviso = screen.getByRole("note", { name: /alergias/i });
    expect(aviso.textContent).toContain("Alergias:");
    expect(aviso.textContent).toContain("Penicilina y látex");
  });

  it("avisa expresamente cuando no estan relevadas", () => {
    render(<AlergiasAviso alergias={null} />);
    expect(screen.getByRole("note", { name: /alergias/i }).textContent).toMatch(/alergias no relevadas/i);
  });
});

describe("OdontogramaPage", () => {
  it("carga historia y catalogo en paralelo y muestra el aviso antes de la grilla", async () => {
    const fetchMock = stubFetch({ historias: [historia({ alergias: "Penicilina" })], hallazgos: [] });
    montar();
    const aviso = await screen.findByRole("note", { name: /alergias/i });
    expect(aviso.textContent).toContain("Penicilina");
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    // Promise.all: los dos primeros pedidos salen juntos, antes de pedir los hallazgos.
    expect(urls.slice(0, 2).sort()).toEqual(
      [expect.stringContaining("/historias?paciente_id=3"), expect.stringContaining("/odontograma/catalogo")].sort(),
    );
    expect(urls[2]).toContain("/odontograma/7/hallazgos?incluir_anulados=true");
    const grilla = screen.getAllByRole("group", { name: /Superior derecho/ })[0] as HTMLElement;
    expect(aviso.compareDocumentPosition(grilla) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("alergias null: el aviso dice que no estan relevadas", async () => {
    stubFetch({ historias: [historia({ alergias: null })], hallazgos: [] });
    montar();
    expect((await screen.findByRole("note", { name: /alergias/i })).textContent).toMatch(/no relevadas/i);
  });

  it("el aviso sigue visible al abrir el detalle de una pieza", async () => {
    const usuario = userEvent.setup();
    stubFetch({
      historias: [historia({ alergias: "Penicilina" })],
      hallazgos: [hallazgo({ pieza_fdi: 16, estado: "caries" })],
    });
    montar();
    await usuario.click(await screen.findByRole("button", { name: /^Pieza 16/ }));
    expect(screen.getByRole("region", { name: /detalle de la pieza 16/i })).toBeDefined();
    expect(screen.getByRole("note", { name: /alergias/i }).textContent).toContain("Penicilina");
  });

  it("secretaria sin historia ve un mensaje y ningun boton para abrirla", async () => {
    stubFetch({ historias: [], hallazgos: [] });
    montar("secretaria");
    expect(await screen.findByText(/no tiene historia clínica/i)).toBeDefined();
    expect(screen.queryByRole("button", { name: /abrir historia/i })).toBeNull();
  });

  it("odontologo sin historia puede abrirla y pasa a ver la grilla", async () => {
    const usuario = userEvent.setup();
    const fetchMock = stubFetch({ historias: [], hallazgos: [] });
    montar("odontologo");
    await usuario.click(await screen.findByRole("button", { name: /abrir historia/i }));
    expect(await screen.findByRole("note", { name: /alergias/i })).toBeDefined();
    const alta = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST");
    expect(JSON.parse(String((alta?.[1] as RequestInit).body))).toMatchObject({ paciente_id: 3 });
    expect(screen.getAllByRole("button", { name: /^Pieza \d\d/ })).toHaveLength(32);
  });

  it("el odontologo edita antecedentes y alergias y el aviso se actualiza", async () => {
    const usuario = userEvent.setup();
    const fetchMock = stubFetch({ historias: [historia({ alergias: null })], hallazgos: [] });
    montar("odontologo");
    await screen.findByRole("note", { name: /alergias/i });
    await usuario.type(screen.getByLabelText("Alergias"), "Ibuprofeno");
    await usuario.type(screen.getByLabelText("Antecedentes"), "Hipertensión");
    await usuario.click(screen.getByRole("button", { name: /guardar historia/i }));
    expect((await screen.findByRole("note", { name: /alergias/i })).textContent).toContain("Ibuprofeno");
    const patch = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "PATCH");
    expect(JSON.parse(String((patch?.[1] as RequestInit).body))).toEqual({
      antecedentes: "Hipertensión",
      alergias: "Ibuprofeno",
    });
  });

  it("la secretaria ve la historia en solo lectura: sin formulario de antecedentes", async () => {
    stubFetch({ historias: [historia({ alergias: "Látex", antecedentes: "Asma" })], hallazgos: [] });
    montar("secretaria");
    const aviso = await screen.findByRole("note", { name: /alergias/i });
    expect(aviso.textContent).toContain("Látex");
    expect(screen.queryByRole("button", { name: /guardar historia/i })).toBeNull();
    expect(screen.getByText(/Asma/)).toBeDefined();
  });

  it("muestra el estado vigente de cada pieza en la grilla", async () => {
    stubFetch({
      historias: [historia()],
      hallazgos: [hallazgo({ pieza_fdi: 16, cara: "oclusal", estado: "obturacion" })],
    });
    montar();
    const celda = await screen.findByRole("button", { name: /^Pieza 16/ });
    expect(within(celda).getByText(/Obturación/)).toBeDefined();
  });

  it("si la API falla muestra una alerta", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.resolve(respuestaJson({ detail: "sin turno vigente con el paciente" }, 403))),
    );
    montar();
    expect((await screen.findByRole("alert")).textContent).toContain("sin turno vigente con el paciente");
  });
});
