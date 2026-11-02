import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LiquidacionesPage } from "./LiquidacionesPage";
import { detalle, item, liquidacion, obraSocial, plan, respuestaJson } from "./testing";
import type { LiquidacionDetalle } from "./tipos";

interface Mundo {
  lista: ReturnType<typeof liquidacion>[];
  detalles: Record<number, LiquidacionDetalle>;
  forzadas?: Record<string, Response>;
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    const forzada = mundo.forzadas?.[`${metodo} ${ruta}`];
    if (forzada !== undefined) return Promise.resolve(forzada.clone());
    if (ruta === "/liquidaciones" && metodo === "GET") return Promise.resolve(respuestaJson(mundo.lista));
    if (ruta === "/obras-sociales" && metodo === "GET") return Promise.resolve(respuestaJson([obraSocial()]));
    if (ruta === "/liquidaciones" && metodo === "POST") {
      const nueva = detalle({ id: 9 });
      mundo.detalles[9] = nueva;
      mundo.lista = [nueva, ...mundo.lista];
      return Promise.resolve(respuestaJson(nueva, 201));
    }
    const una = /^\/liquidaciones\/(\d+)(?:\/([a-z-]+))?$/.exec(ruta);
    if (una !== null) {
      const id = Number(una[1]);
      const actual = mundo.detalles[id];
      if (actual === undefined) return Promise.resolve(respuestaJson({ detail: "liquidación inexistente" }, 404));
      if (una[2] === undefined && metodo === "GET") return Promise.resolve(respuestaJson(actual));
      if (una[2] === "presentar") return Promise.resolve(respuestaJson((mundo.detalles[id] = { ...actual, estado: "presentada" })));
      if (una[2] === "cobrar") return Promise.resolve(respuestaJson((mundo.detalles[id] = { ...actual, estado: "cobrada" })));
      if (una[2] === "revertir-cobro") {
        return Promise.resolve(respuestaJson((mundo.detalles[id] = { ...actual, estado: "presentada", revertida: true })));
      }
      if (una[2] === "descartar") {
        delete mundo.detalles[id];
        mundo.lista = mundo.lista.filter((l) => l.id !== id);
        return Promise.resolve(new Response(null, { status: 204 }));
      }
    }
    const archivo = /^\/liquidaciones\/(\d+)\/export\.(csv|pdf)$/.exec(ruta);
    if (archivo !== null) return Promise.resolve(new Response("contenido", { status: 200 }));
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const mundoBase = (parcial: Partial<LiquidacionDetalle> = {}): Mundo => {
  const d = detalle(parcial);
  return { lista: [d], detalles: { [d.id]: d } };
};

const botones = (): string[] => screen.queryAllByRole("button").map((b) => b.textContent ?? "");

async function abrirPrimera(): Promise<void> {
  const lista = await screen.findByRole("list", { name: "Liquidaciones" });
  await userEvent.click(within(lista).getAllByRole("button", { name: /Ver liquidación/ })[0] as HTMLElement);
  await screen.findByRole("region", { name: /Detalle de la liquidación/ });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LiquidacionesPage: lista y detalle", () => {
  it("el admin ve la lista con obra social, periodo, estado en texto y total", async () => {
    stubFetch(mundoBase());
    render(<LiquidacionesPage rol="admin" />);
    const fila = within(await screen.findByRole("list", { name: "Liquidaciones" })).getAllByRole("listitem")[0];
    expect(fila?.textContent).toContain("OS Ficticia Demo");
    expect(fila?.textContent).toContain("10/2026");
    expect(fila?.textContent).toContain("Borrador");
    expect(fila?.textContent).toContain("$ 10.500,00");
  });

  it("el detalle agrupa por plan con subtotal y senala la revision con texto, no solo color", async () => {
    stubFetch(mundoBase({
      planes: [
        plan({ plan_nombre: "Plan Base", subtotal: "10500.00", items: [item(), item({ revision: true, monto: "0.00", paciente_nombre: "Inventado, Beto" })] }),
        plan({ plan_id: 2, plan_nombre: "Plan Plus", subtotal: "0.00", items: [] }),
      ],
      cantidad_items: 2,
      cantidad_revision: 1,
    }));
    render(<LiquidacionesPage rol="admin" />);
    await abrirPrimera();
    const region = screen.getByRole("region", { name: /Detalle de la liquidación/ });
    expect(within(region).getByRole("heading", { name: /Plan Base/ })).toBeDefined();
    expect(within(region).getByText(/Subtotal Plan Base/).textContent).toContain("$ 10.500,00");
    const filas = within(region).getAllByRole("listitem");
    const enRevision = filas.find((f) => f.textContent?.includes("Inventado, Beto"));
    expect(enRevision?.textContent).toMatch(/Para revisión manual/);
    expect(enRevision?.textContent).toMatch(/No se liquida/);
    expect(within(region).getByRole("status", { name: "Aviso de revisión" }).textContent).toMatch(/1 prestación/);
  });

  it("el odontologo ve la pantalla solo de lectura, sin formulario ni acciones", async () => {
    const fetchMock = stubFetch(mundoBase({ estado: "presentada" }));
    render(<LiquidacionesPage rol="odontologo" />);
    await abrirPrimera();
    expect(screen.getByText(/solo lectura/i)).toBeDefined();
    expect(screen.queryByRole("form", { name: "Generar liquidación" })).toBeNull();
    expect(botones().join("|")).not.toMatch(/Presentar|Descartar|Cobrar|Exportar|Revertir|Generar/);
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/obras-sociales"))).toBe(false);
  });

  it("un error al cargar se muestra como alerta", async () => {
    stubFetch({ ...mundoBase(), forzadas: { "GET /liquidaciones": respuestaJson({ detail: "sin permiso" }, 403) } });
    render(<LiquidacionesPage rol="admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("sin permiso");
  });

  it("sin liquidaciones lo dice con texto", async () => {
    stubFetch({ lista: [], detalles: {} });
    render(<LiquidacionesPage rol="admin" />);
    expect(await screen.findByText(/Todavía no hay liquidaciones/)).toBeDefined();
  });
});

describe("LiquidacionesPage: generar", () => {
  it("valida el periodo antes de enviar y no llama al servidor", async () => {
    const fetchMock = stubFetch(mundoBase());
    render(<LiquidacionesPage rol="admin" />);
    const form = await screen.findByRole("form", { name: "Generar liquidación" });
    await userEvent.type(within(form).getByLabelText("Período (AAAA-MM)"), "2026-13");
    await userEvent.click(within(form).getByRole("button", { name: "Generar" }));
    expect((await within(form).findByRole("alert")).textContent).toMatch(/AAAA-MM/);
    expect(fetchMock.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === "POST")).toBe(false);
  });

  it("genera por obra social y periodo y muestra el borrador creado", async () => {
    const fetchMock = stubFetch(mundoBase());
    render(<LiquidacionesPage rol="admin" />);
    const form = await screen.findByRole("form", { name: "Generar liquidación" });
    await userEvent.selectOptions(within(form).getByLabelText("Obra social"), "1");
    await userEvent.type(within(form).getByLabelText("Período (AAAA-MM)"), "2026-10");
    await userEvent.click(within(form).getByRole("button", { name: "Generar" }));
    expect(await screen.findByRole("region", { name: /Detalle de la liquidación/ })).toBeDefined();
    const post = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST") as [string, RequestInit];
    expect(JSON.parse(String(post[1].body))).toEqual({ os_id: 1, periodo: "2026-10" });
  });

  it("si no hay prestaciones (409) muestra el mensaje del servidor", async () => {
    stubFetch({
      ...mundoBase(),
      forzadas: { "POST /liquidaciones": respuestaJson({ detail: "no hay prestaciones para liquidar en el período" }, 409) },
    });
    render(<LiquidacionesPage rol="admin" />);
    const form = await screen.findByRole("form", { name: "Generar liquidación" });
    await userEvent.type(within(form).getByLabelText("Período (AAAA-MM)"), "2025-01");
    await userEvent.click(within(form).getByRole("button", { name: "Generar" }));
    expect((await within(form).findByRole("alert")).textContent).toContain("no hay prestaciones");
  });
});

describe("LiquidacionesPage: acciones", () => {
  it("un borrador se presenta y pasa a presentada; solo ofrece las acciones que le corresponden", async () => {
    stubFetch(mundoBase());
    render(<LiquidacionesPage rol="admin" />);
    await abrirPrimera();
    expect(botones().join("|")).toMatch(/Presentar/);
    expect(botones().join("|")).toMatch(/Descartar/);
    expect(botones().join("|")).not.toMatch(/Cobrar liquidación|Revertir/);
    await userEvent.click(screen.getByRole("button", { name: "Presentar" }));
    expect(await screen.findByText("Presentada")).toBeDefined();
    expect(botones().join("|")).not.toContain("Descartar");
    expect(botones().join("|")).toMatch(/Cobrar liquidación/);
  });

  it("descartar un borrador lo saca de la lista", async () => {
    stubFetch(mundoBase());
    render(<LiquidacionesPage rol="admin" />);
    await abrirPrimera();
    await userEvent.click(screen.getByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: /Detalle de la liquidación/ })).toBeNull());
    expect(await screen.findByText(/Todavía no hay liquidaciones/)).toBeDefined();
  });

  it("cobra con el medio elegido", async () => {
    const fetchMock = stubFetch(mundoBase({ estado: "presentada" }));
    render(<LiquidacionesPage rol="admin" />);
    await abrirPrimera();
    await userEvent.selectOptions(screen.getByLabelText("Medio de cobro"), "efectivo");
    await userEvent.click(screen.getByRole("button", { name: "Cobrar liquidación" }));
    expect(await screen.findByText("Cobrada")).toBeDefined();
    const post = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/cobrar")) as [string, RequestInit];
    expect(JSON.parse(String(post[1].body))).toEqual({ medio: "efectivo" });
  });

  it("si el servidor rechaza el cobro (409) muestra el mensaje sin perder el medio elegido", async () => {
    stubFetch({
      ...mundoBase({ estado: "presentada" }),
      forzadas: { "POST /liquidaciones/7/cobrar": respuestaJson({ detail: "hay una caja anterior sin cerrar" }, 409) },
    });
    render(<LiquidacionesPage rol="admin" />);
    await abrirPrimera();
    const medio = screen.getByLabelText("Medio de cobro") as HTMLSelectElement;
    await userEvent.selectOptions(medio, "tarjeta_simulada");
    await userEvent.click(screen.getByRole("button", { name: "Cobrar liquidación" }));
    expect((await screen.findByRole("alert")).textContent).toContain("hay una caja anterior sin cerrar");
    expect((screen.getByLabelText("Medio de cobro") as HTMLSelectElement).value).toBe("tarjeta_simulada");
    expect(screen.getByText("Presentada")).toBeDefined();
  });

  it("una liquidacion con total cero no ofrece cobrar y lo explica", async () => {
    stubFetch(mundoBase({ estado: "presentada", total: "0.00", cantidad_revision: 1 }));
    render(<LiquidacionesPage rol="admin" />);
    await abrirPrimera();
    expect(screen.queryByRole("button", { name: "Cobrar liquidación" })).toBeNull();
    expect(screen.getByText(/no tiene importe para cobrar/i)).toBeDefined();
  });

  it("exporta CSV y PDF con la sesion autenticada y guarda el archivo", async () => {
    const guardar = vi.fn();
    const fetchMock = stubFetch(mundoBase({ estado: "presentada" }));
    render(<LiquidacionesPage rol="admin" guardar={guardar} />);
    await abrirPrimera();
    await userEvent.click(screen.getByRole("button", { name: "Exportar CSV" }));
    await waitFor(() => expect(guardar).toHaveBeenCalledTimes(1));
    expect(guardar.mock.calls[0]?.[1]).toBe("liquidacion-7.csv");
    await userEvent.click(screen.getByRole("button", { name: "Exportar PDF" }));
    await waitFor(() => expect(guardar).toHaveBeenCalledTimes(2));
    expect(guardar.mock.calls[1]?.[1]).toBe("liquidacion-7.pdf");
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/liquidaciones/7/export.pdf"))).toBe(true);
  });

  it("revertir un cobro exige motivo y deja la liquidacion presentada y revertida", async () => {
    const fetchMock = stubFetch(mundoBase({ estado: "cobrada" }));
    render(<LiquidacionesPage rol="admin" />);
    await abrirPrimera();
    await userEvent.click(screen.getByRole("button", { name: "Revertir cobro" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar reversión" }));
    expect((await screen.findByRole("alert")).textContent).toContain("El motivo es obligatorio");
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/revertir-cobro"))).toBe(false);
    await userEvent.type(screen.getByLabelText("Motivo de la reversión"), "cobro duplicado");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar reversión" }));
    expect(await screen.findByText(/Cobro revertido: no se puede volver a cobrar/)).toBeDefined();
    const post = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/revertir-cobro")) as [string, RequestInit];
    expect(JSON.parse(String(post[1].body))).toEqual({ motivo: "cobro duplicado" });
    expect(screen.queryByRole("button", { name: "Cobrar liquidación" })).toBeNull();
  });
});
