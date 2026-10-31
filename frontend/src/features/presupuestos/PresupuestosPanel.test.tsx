import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { hallazgo } from "../odontograma/testing";
import { PresupuestosPanel } from "./PresupuestosPanel";
import { item, presupuesto, respuestaJson, TRATAMIENTOS } from "./testing";
import type { Presupuesto } from "./tipos";

const HALLAZGOS = [hallazgo({ id: 11, pieza_fdi: 16, cara: "oclusal", estado: "caries" })];
const NOMBRES = { caries: "Caries" };

interface Mundo {
  lista: Presupuesto[];
  /** Respuestas forzadas por ruta (por ejemplo un 409). */
  forzadas?: Record<string, Response>;
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    const forzada = mundo.forzadas?.[`${metodo} ${ruta}`];
    if (forzada !== undefined) return Promise.resolve(forzada.clone());
    if (ruta.startsWith("/presupuestos?paciente_id=")) return Promise.resolve(respuestaJson(mundo.lista));
    if (ruta === "/tratamientos") return Promise.resolve(respuestaJson(TRATAMIENTOS));
    if (ruta === "/presupuestos" && metodo === "POST") {
      const nuevo = presupuesto({ id: 900, total: "18000.00", items: [item()] });
      mundo.lista = [nuevo, ...mundo.lista];
      return Promise.resolve(respuestaJson(nuevo, 201));
    }
    const transicion = /^\/presupuestos\/(\d+)\/(presentar|aceptar|rechazar|baja)$/.exec(ruta);
    if (transicion !== null && metodo === "POST") {
      const id = Number(transicion[1]);
      const actual = mundo.lista.find((p) => p.id === id) as Presupuesto;
      const cuerpo = init?.body === undefined ? {} : (JSON.parse(String(init.body)) as Record<string, string>);
      const estado = { presentar: "presentado", aceptar: "aceptado", rechazar: "rechazado", baja: actual.estado }[
        transicion[2] as "presentar" | "aceptar" | "rechazar" | "baja"
      ] as Presupuesto["estado"];
      const nuevo = { ...actual, estado, motivo_rechazo: cuerpo["motivo"] ?? null };
      mundo.lista = mundo.lista.map((p) => (p.id === id ? nuevo : p));
      return Promise.resolve(respuestaJson(nuevo));
    }
    if (/^\/presupuestos\/\d+$/.test(ruta) && metodo === "PUT") {
      const id = Number(ruta.split("/")[2]);
      const actual = mundo.lista.find((p) => p.id === id) as Presupuesto;
      const nuevo = { ...actual, total: "54000.00" };
      mundo.lista = mundo.lista.map((p) => (p.id === id ? nuevo : p));
      return Promise.resolve(respuestaJson(nuevo));
    }
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function montar(rol: "odontologo" | "secretaria" = "odontologo", hallazgos = HALLAZGOS): void {
  render(<PresupuestosPanel pacienteId={3} hallazgos={hallazgos} nombres={NOMBRES} rol={rol} />);
}

async function abrir(nombre: RegExp): Promise<void> {
  await userEvent.click(await screen.findByRole("button", { name: nombre }));
}

const botones = (): string[] => screen.queryAllByRole("button").map((b) => b.textContent ?? "");

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PresupuestosPanel", () => {
  it("estado con texto en la lista, del mas reciente al mas antiguo", async () => {
    stubFetch({ lista: [presupuesto({ id: 2, estado: "presentado" }), presupuesto({ id: 1, estado: "rechazado" })] });
    montar();
    const lista = await screen.findByRole("list", { name: "Lista de presupuestos" });
    const filas = within(lista).getAllByRole("listitem");
    expect(filas[0]?.textContent).toContain("Presentado");
    expect(filas[1]?.textContent).toContain("Rechazado");
    expect(filas[0]?.textContent).toContain("$ 36.000,00");
  });

  it("sin presupuestos lo dice con texto", async () => {
    stubFetch({ lista: [] });
    montar();
    expect(await screen.findByText(/no tiene presupuestos/i)).toBeTruthy();
  });

  it("secretaria sin controles: ve lista y detalle pero no puede crear ni cambiar estados", async () => {
    stubFetch({ lista: [presupuesto({ id: 5, estado: "presentado", es_propio: false })] });
    montar("secretaria");
    await abrir(/Presupuesto 5/);
    expect(screen.getByLabelText("Estado del presupuesto").textContent).toBe("Presentado");
    const textos = botones().join("|");
    for (const prohibido of ["Nuevo presupuesto", "Presentar", "Aceptar", "Rechazar", "Dar de baja", "Editar"]) {
      expect(textos).not.toContain(prohibido);
    }
  });

  it("secretaria no pide el catalogo de tratamientos", async () => {
    const fetchMock = stubFetch({ lista: [] });
    montar("secretaria");
    await screen.findByText(/no tiene presupuestos/i);
    expect(fetchMock.mock.calls.map((c) => String(c[0])).some((u) => u.endsWith("/tratamientos"))).toBe(false);
  });

  it("solo el autor ve acciones: un colega vinculado solo lee", async () => {
    stubFetch({ lista: [presupuesto({ id: 6, estado: "presentado", es_propio: false })] });
    montar("odontologo");
    await abrir(/Presupuesto 6/);
    const textos = botones().join("|");
    expect(textos).not.toMatch(/Aceptar|Rechazar|Presentar|Dar de baja|Editar/);
    expect(textos).toContain("Nuevo presupuesto");
  });

  it("el autor ve las acciones segun el estado", async () => {
    stubFetch({
      lista: [
        presupuesto({ id: 7, estado: "borrador" }),
        presupuesto({ id: 8, estado: "presentado" }),
        presupuesto({ id: 9, estado: "aceptado" }),
      ],
    });
    montar();
    await abrir(/Presupuesto 7/);
    expect(botones()).toEqual(expect.arrayContaining(["Presentar", "Editar ítems", "Dar de baja"]));
    expect(botones()).not.toContain("Aceptar");
    await abrir(/Presupuesto 8/);
    expect(botones()).toEqual(expect.arrayContaining(["Aceptar", "Rechazar"]));
    expect(botones()).not.toContain("Presentar");
    await abrir(/Presupuesto 9/);
    expect(botones()).not.toEqual(expect.arrayContaining(["Aceptar"]));
    expect(botones()).not.toContain("Rechazar");
  });

  it("aceptar actualiza el estado en pantalla", async () => {
    stubFetch({ lista: [presupuesto({ id: 8, estado: "presentado" })] });
    montar();
    await abrir(/Presupuesto 8/);
    await userEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    expect((await screen.findAllByText("Aceptado")).length).toBeGreaterThan(0);
    expect(botones()).not.toContain("Aceptar");
  });

  it("rechazo sin motivo no envia e indica que es obligatorio", async () => {
    const fetchMock = stubFetch({ lista: [presupuesto({ id: 8, estado: "presentado" })] });
    montar();
    await abrir(/Presupuesto 8/);
    await userEvent.click(screen.getByRole("button", { name: "Rechazar" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar rechazo" }));
    expect((await screen.findByRole("alert")).textContent).toContain("El motivo es obligatorio");
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/rechazar"))).toBe(false);
  });

  it("rechazo con motivo lo envia en el cuerpo y deja el presupuesto rechazado", async () => {
    const fetchMock = stubFetch({ lista: [presupuesto({ id: 8, estado: "presentado" })] });
    montar();
    await abrir(/Presupuesto 8/);
    await userEvent.click(screen.getByRole("button", { name: "Rechazar" }));
    await userEvent.type(screen.getByLabelText("Motivo del rechazo"), "Prefiere esperar");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar rechazo" }));
    expect((await screen.findAllByText("Rechazado")).length).toBeGreaterThan(0);
    const llamada = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/rechazar")) as [string, RequestInit];
    expect(llamada[0]).not.toContain("esperar");
    expect(JSON.parse(String(llamada[1].body))).toEqual({ motivo: "Prefiere esperar" });
  });

  it("409 mantiene la pantalla: muestra el mensaje y el presupuesto sigue operable", async () => {
    stubFetch({
      lista: [presupuesto({ id: 8, estado: "presentado" })],
      forzadas: {
        "POST /presupuestos/8/aceptar": respuestaJson(
          { detail: "un hallazgo del presupuesto fue corregido o dado de baja" },
          409,
        ),
      },
    });
    montar();
    await abrir(/Presupuesto 8/);
    await userEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    expect((await screen.findByRole("alert")).textContent).toContain("corregido o dado de baja");
    expect(screen.getByLabelText("Estado del presupuesto").textContent).toBe("Presentado");
    expect(botones()).toEqual(expect.arrayContaining(["Aceptar", "Rechazar"]));
  });

  it("hallazgo no vigente visible en el detalle", async () => {
    stubFetch({
      lista: [presupuesto({ id: 8, estado: "aceptado", items: [item({ hallazgo_vigente: false })] })],
    });
    montar();
    await abrir(/Presupuesto 8/);
    expect(screen.getByText(/ya no está vigente/i)).toBeTruthy();
  });

  it("admin sin pieza: el detalle no muestra datos clinicos que no recibio", async () => {
    stubFetch({
      lista: [presupuesto({ id: 8, items: [item({ pieza_fdi: null, cara: null })], es_propio: false })],
    });
    montar("secretaria");
    await abrir(/Presupuesto 8/);
    expect(screen.queryByText(/Pieza/)).toBeNull();
  });

  it("nuevo presupuesto: solo hallazgos activos y el total que devuelve el servidor", async () => {
    const fetchMock = stubFetch({ lista: [] });
    const anulado = hallazgo({ id: 12, pieza_fdi: 26, cara: "mesial", estado: "caries", deleted_at: "2026-10-20T10:00:00Z", motivo_baja: "x" });
    montar("odontologo", [...HALLAZGOS, anulado]);
    await abrir(/Nuevo presupuesto/);
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    expect(screen.queryByRole("option", { name: /Pieza 26/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    expect((await screen.findAllByText(/\$ 18\.000,00/)).length).toBeGreaterThan(0);
    const alta = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST") as [string, RequestInit];
    const cuerpo = JSON.parse(String(alta[1].body)) as Record<string, unknown>;
    expect(cuerpo).toEqual({ paciente_id: 3, items: [{ hallazgo_id: 11, tratamiento_id: 1, cantidad: 1 }] });
  });

  it("sin hallazgos activos no se ofrece crear y se explica por que", async () => {
    stubFetch({ lista: [] });
    montar("odontologo", []);
    await screen.findByText(/no tiene presupuestos/i);
    const boton = screen.getByRole("button", { name: "Nuevo presupuesto" }) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    expect(screen.getByText(/hallazgos activos/i)).toBeTruthy();
  });

  it("baja de un borrador pide motivo y lo saca de la lista", async () => {
    stubFetch({ lista: [presupuesto({ id: 7, estado: "borrador" })] });
    montar();
    await abrir(/Presupuesto 7/);
    await userEvent.click(screen.getByRole("button", { name: "Dar de baja" }));
    await userEvent.type(screen.getByLabelText("Motivo de la baja"), "Duplicado");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar baja" }));
    expect(await screen.findByText(/no tiene presupuestos/i)).toBeTruthy();
  });

  it("un error al cargar se muestra como alerta", async () => {
    stubFetch({ lista: [], forzadas: { "GET /presupuestos?paciente_id=3": respuestaJson({ detail: "sin turno vigente con el paciente" }, 403) } });
    montar();
    expect((await screen.findByRole("alert")).textContent).toContain("sin turno vigente");
  });
});
