import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { presupuesto } from "../presupuestos/testing";
import { CuentaPage } from "./CuentaPage";
import { cuenta, movimiento, respuestaJson } from "./testing";
import type { Cuenta } from "./tipos";

interface Mundo {
  cuenta: Cuenta;
  forzadas?: Record<string, Response>;
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    const forzada = mundo.forzadas?.[`${metodo} ${ruta}`];
    if (forzada !== undefined) return Promise.resolve(forzada.clone());
    if (ruta === "/cuentas/3" && metodo === "GET") return Promise.resolve(respuestaJson(mundo.cuenta));
    const anular = /^\/cuentas\/3\/movimientos\/(\d+)\/anular$/.exec(ruta);
    if (anular !== null && metodo === "POST") {
      const original = mundo.cuenta.movimientos.find((m) => m.id === Number(anular[1]));
      const contra = movimiento({
        id: 999, tipo: "ajuste", monto: `-${original?.monto ?? "0.00"}`, anula_a_id: Number(anular[1]),
        motivo: "x", concepto: "Anulación",
      });
      mundo.cuenta = {
        ...mundo.cuenta,
        saldo: "0.00",
        movimientos: [contra, ...mundo.cuenta.movimientos.map((m) => (m.id === original?.id ? { ...m, anulado: true } : m))],
      };
      return Promise.resolve(respuestaJson(contra, 201));
    }
    if (ruta === "/presupuestos/31") return Promise.resolve(respuestaJson(presupuesto({ id: 31, estado: "aceptado" })));
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function montar(rol: "secretaria" | "admin" = "secretaria"): { alVolver: ReturnType<typeof vi.fn> } {
  const alVolver = vi.fn();
  render(<CuentaPage pacienteId={3} pacienteNombre="Ana Ficticia" rol={rol} alVolver={alVolver} />);
  return { alVolver };
}

const botones = (): string[] => screen.queryAllByRole("button").map((b) => b.textContent ?? "");

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CuentaPage", () => {
  it("debe: lo dice con texto y muestra el importe formateado", async () => {
    stubFetch({ cuenta: cuenta({ saldo: "500.00" }) });
    montar();
    const estado = await screen.findByRole("status");
    expect(estado.textContent).toContain("El paciente debe");
    expect(estado.textContent).toContain("$ 500,00");
  });

  it("sin deuda: lo dice con texto", async () => {
    stubFetch({ cuenta: cuenta({ saldo: "0.00", movimientos: [movimiento({ anulado: true })] }) });
    montar();
    expect((await screen.findByRole("status")).textContent).toContain("sin deuda");
  });

  it("saldo a favor: lo dice con texto y muestra el importe sin signo", async () => {
    stubFetch({ cuenta: cuenta({ saldo: "-200.50" }) });
    montar();
    const estado = await screen.findByRole("status");
    expect(estado.textContent).toContain("saldo a favor");
    expect(estado.textContent).toContain("$ 200,50");
    expect(estado.textContent).not.toContain("-");
  });

  it("sin movimientos: lo dice con texto y no hay lista", async () => {
    stubFetch({ cuenta: cuenta({ saldo: "0.00", movimientos: [] }) });
    montar();
    expect(await screen.findByText(/no tiene movimientos/i)).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Movimientos" })).toBeNull();
  });

  it("anulado visible: el cargo lleva la marca y el contramovimiento indica a cual anula", async () => {
    const cargo = movimiento({ id: 10, anulado: true });
    const contra = movimiento({ id: 11, tipo: "ajuste", monto: "-36000.00", anula_a_id: 10, motivo: "Error de carga", concepto: "Anulación" });
    stubFetch({ cuenta: cuenta({ saldo: "0.00", movimientos: [contra, cargo] }) });
    montar();
    const items = within(await screen.findByRole("list", { name: "Movimientos" })).getAllByRole("listitem");
    expect(items[0]?.textContent).toContain("Anula el movimiento 10");
    expect(items[0]?.textContent).toContain("Error de carga");
    expect(items[0]?.textContent).toContain("-$ 36.000,00");
    expect(items[1]?.textContent).toContain("Anulado");
  });

  it("secretaria sin anular: ve cargos y anulaciones pero no la accion", async () => {
    stubFetch({ cuenta: cuenta() });
    montar("secretaria");
    await screen.findByRole("list", { name: "Movimientos" });
    expect(botones().join("|")).not.toContain("Anular");
  });

  it("admin ve la accion de anular solo en cargos sin anular", async () => {
    stubFetch({
      cuenta: cuenta({
        movimientos: [
          movimiento({ id: 1 }),
          movimiento({ id: 2, anulado: true }),
          movimiento({ id: 3, tipo: "ajuste", monto: "-5.00", anula_a_id: 2, motivo: "x" }),
          movimiento({ id: 4, tipo: "pago", monto: "-10.00", presupuesto_id: null, recibo_id: 8 }),
        ],
      }),
    });
    montar("admin");
    await screen.findByRole("list", { name: "Movimientos" });
    expect(screen.getAllByRole("button", { name: /^Anular cargo/ })).toHaveLength(1);
  });

  it("anular sin motivo no envia e indica que es obligatorio", async () => {
    const fetchMock = stubFetch({ cuenta: cuenta() });
    montar("admin");
    await userEvent.click(await screen.findByRole("button", { name: /^Anular cargo/ }));
    const dialogo = screen.getByRole("dialog", { name: "Anular cargo" });
    await userEvent.click(within(dialogo).getByRole("button", { name: "Confirmar anulación" }));
    expect((await within(dialogo).findByRole("alert")).textContent).toContain("El motivo es obligatorio");
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/anular"))).toBe(false);
  });

  it("admin anula con motivo en el cuerpo y la pantalla refleja el saldo que dice el servidor", async () => {
    const fetchMock = stubFetch({ cuenta: cuenta({ saldo: "36000.00", movimientos: [movimiento({ id: 10 })] }) });
    montar("admin");
    await userEvent.click(await screen.findByRole("button", { name: /^Anular cargo/ }));
    await userEvent.type(screen.getByLabelText("Motivo de la anulación"), "Cargado por error");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    expect((await screen.findByRole("status")).textContent).toContain("sin deuda");
    expect(screen.queryByRole("dialog")).toBeNull();
    const llamada = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/anular")) as [string, RequestInit];
    expect(llamada[0]).not.toContain("error");
    expect(JSON.parse(String(llamada[1].body))).toEqual({ motivo: "Cargado por error" });
    expect(botones().join("|")).not.toContain("Anular cargo");
  });

  it("un 409 al anular muestra el mensaje y deja el dialogo abierto", async () => {
    stubFetch({
      cuenta: cuenta({ movimientos: [movimiento({ id: 10 })] }),
      forzadas: { "POST /cuentas/3/movimientos/10/anular": respuestaJson({ detail: "el cargo ya fue anulado" }, 409) },
    });
    montar("admin");
    await userEvent.click(await screen.findByRole("button", { name: /^Anular cargo/ }));
    await userEvent.type(screen.getByLabelText("Motivo de la anulación"), "Otra vez");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    const dialogo = screen.getByRole("dialog", { name: "Anular cargo" });
    expect((await within(dialogo).findByRole("alert")).textContent).toContain("el cargo ya fue anulado");
  });

  it("cancelar el dialogo no anula nada", async () => {
    const fetchMock = stubFetch({ cuenta: cuenta() });
    montar("admin");
    await userEvent.click(await screen.findByRole("button", { name: /^Anular cargo/ }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/anular"))).toBe(false);
  });

  it("abre presupuesto en lectura desde un cargo", async () => {
    stubFetch({ cuenta: cuenta() });
    montar("secretaria");
    await userEvent.click(await screen.findByRole("button", { name: "Ver presupuesto 31" }));
    const detalle = await screen.findByRole("article", { name: "Presupuesto 31" });
    expect(within(detalle).getByLabelText("Estado del presupuesto").textContent).toBe("Aceptado");
    // solo lectura: ninguna accion de estado
    expect(botones().join("|")).not.toMatch(/Aceptar|Rechazar|Presentar|Editar/);
  });

  it("un movimiento sin presupuesto no ofrece el acceso", async () => {
    stubFetch({ cuenta: cuenta({ movimientos: [movimiento({ presupuesto_id: null, tipo: "pago", monto: "-1.00" })] }) });
    montar();
    await screen.findByRole("list", { name: "Movimientos" });
    expect(botones().join("|")).not.toContain("Ver presupuesto");
  });

  it("un error al cargar se muestra como alerta", async () => {
    stubFetch({ cuenta: cuenta(), forzadas: { "GET /cuentas/3": respuestaJson({ detail: "sin permiso" }, 403) } });
    montar();
    expect((await screen.findByRole("alert")).textContent).toContain("sin permiso");
  });

  it("volver invoca la salida", async () => {
    stubFetch({ cuenta: cuenta() });
    const { alVolver } = montar();
    await userEvent.click(await screen.findByRole("button", { name: "Volver a la agenda" }));
    expect(alVolver).toHaveBeenCalledTimes(1);
  });
});
