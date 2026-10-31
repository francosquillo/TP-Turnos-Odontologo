import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CajaPage } from "./CajaPage";
import { caja, estadoCaja, recibo, respuestaJson } from "./testing";
import type { EstadoCaja, Recibo } from "./tipos";

interface Mundo {
  estado: EstadoCaja;
  recibos?: Recibo[];
  porFecha?: Record<string, { estado: EstadoCaja; recibos: Recibo[] }>;
  forzadas?: Record<string, Response>;
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    const forzada = mundo.forzadas?.[`${metodo} ${ruta}`];
    if (forzada !== undefined) return Promise.resolve(forzada.clone());
    const consulta = /^\/caja(?:\?fecha=(.+))?$/.exec(ruta);
    if (consulta !== null && metodo === "GET") {
      const otra = consulta[1] === undefined ? undefined : mundo.porFecha?.[consulta[1]];
      return Promise.resolve(respuestaJson(otra?.estado ?? mundo.estado));
    }
    const lista = /^\/recibos\?fecha=(.+)$/.exec(ruta);
    if (lista !== null && metodo === "GET") {
      return Promise.resolve(respuestaJson(mundo.porFecha?.[lista[1] ?? ""]?.recibos ?? mundo.recibos ?? []));
    }
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CajaPage", () => {
  it("muestra la fecha operativa formateada, el estado, el total y el desglose por medio", async () => {
    stubFetch({ estado: estadoCaja() });
    render(<CajaPage rol="secretaria" />);
    expect(await screen.findByRole("heading", { name: /Caja del 31\/10\/2026/ })).toBeDefined();
    expect(screen.getByText("Caja abierta")).toBeDefined();
    expect(screen.getByText(/Total del sistema/).textContent).toContain("$ 1.500,00");
    const desglose = within(screen.getByRole("list", { name: "Desglose por medio" })).getAllByRole("listitem");
    expect(desglose.map((li) => li.textContent)).toEqual([
      expect.stringContaining("Efectivo"),
      expect.stringContaining("Transferencia"),
    ]);
    expect(desglose[0]?.textContent).toContain("$ 1.000,00");
  });

  it("la fecha no se corre un dia: el 2026-10-31 se ve como 31/10/2026 y el 2026-01-01 como 01/01/2026", async () => {
    stubFetch({ estado: estadoCaja({ fecha: "2026-01-01", hoy: "2026-01-01", caja: caja({ fecha: "2026-01-01" }) }) });
    render(<CajaPage rol="admin" />);
    expect(await screen.findByRole("heading", { name: /Caja del 01\/01\/2026/ })).toBeDefined();
  });

  it("sin caja: lo dice con texto y no muestra cierre", async () => {
    stubFetch({ estado: estadoCaja({ caja: null, desglose: [] }) });
    render(<CajaPage rol="secretaria" />);
    expect(await screen.findByText(/Todavía no hay movimientos/i)).toBeDefined();
    expect(screen.queryByRole("form", { name: "Cerrar caja" })).toBeNull();
    expect(screen.queryByRole("list", { name: "Desglose por medio" })).toBeNull();
  });

  it("bloqueo por caja pendiente: indica con texto la fecha pendiente y que debe cerrarse", async () => {
    stubFetch({
      estado: estadoCaja({
        fecha: "2026-10-30", hoy: "2026-10-31", operable: false, bloqueo: "caja_pendiente",
        caja: caja({ fecha: "2026-10-30" }),
      }),
    });
    render(<CajaPage rol="secretaria" />);
    const aviso = await screen.findByRole("alert");
    expect(aviso.textContent).toContain("30/10/2026");
    expect(aviso.textContent).toMatch(/cerrarla|cerrala|cerrar/i);
    expect(screen.getByRole("form", { name: "Cerrar caja" })).toBeDefined();
  });

  it("caja cerrada con diferencia: muestra contado y diferencia, sin acciones de cierre", async () => {
    const cerrada = caja({
      estado: "cerrada", total_sistema: "1500.00", total_contado: "1400.00", diferencia: "-100.00",
      motivo_diferencia: "billete roto", cerrada_por: 2, cerrada_at: "2026-10-31T22:00:00Z",
    });
    stubFetch({ estado: estadoCaja({ operable: false, bloqueo: "caja_cerrada", caja: cerrada }) });
    render(<CajaPage rol="secretaria" />);
    expect(await screen.findByText("Caja cerrada")).toBeDefined();
    expect(screen.getByText(/Total contado/).textContent).toContain("$ 1.400,00");
    expect(screen.getByText(/Diferencia/).textContent).toContain("-$ 100,00");
    expect(screen.getByText(/billete roto/)).toBeDefined();
    expect(screen.queryByRole("form", { name: "Cerrar caja" })).toBeNull();
    expect(screen.getByRole("status").textContent).toMatch(/ya está cerrada/i);
  });

  it("error de carga: se informa con un alerta", async () => {
    stubFetch({ estado: estadoCaja(), forzadas: { "GET /caja": respuestaJson({ detail: "sin permiso" }, 403) } });
    render(<CajaPage rol="admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("sin permiso");
  });

  it("los recibos del dia se piden con la fecha de la caja", async () => {
    const fetchMock = stubFetch({ estado: estadoCaja(), recibos: [recibo({ numero: 3 })] });
    render(<CajaPage rol="secretaria" />);
    expect(await screen.findByText(/Recibo N° 3/)).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/recibos?fecha=2026-10-31"))).toBe(true);
  });

  it("el admin ve el estado pero no el formulario de cierre", async () => {
    stubFetch({ estado: estadoCaja() });
    render(<CajaPage rol="admin" />);
    await screen.findByText("Caja abierta");
    expect(screen.queryByRole("form", { name: "Cerrar caja" })).toBeNull();
  });

  it("consultar otra fecha pide caja y recibos de esa fecha", async () => {
    const fetchMock = stubFetch({
      estado: estadoCaja(),
      porFecha: {
        "2026-10-29": {
          estado: estadoCaja({ fecha: "2026-10-29", caja: null, desglose: [], operable: true }),
          recibos: [],
        },
      },
    });
    render(<CajaPage rol="admin" />);
    await screen.findByText("Caja abierta");
    const campo = screen.getByLabelText("Ver otro día");
    await userEvent.clear(campo);
    await userEvent.type(campo, "2026-10-29");
    await userEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByRole("heading", { name: /Caja del 29\/10\/2026/ })).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/caja?fecha=2026-10-29"))).toBe(true);
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/recibos?fecha=2026-10-29"))).toBe(true);
  });
});
