/** C-10 grupo 9.3 y 9.4: cobro y anulacion de recibos desde la cuenta corriente. */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cobro, estadoCaja, recibo } from "../caja/testing";
import type { EstadoCaja } from "../caja/tipos";
import { CuentaPage } from "./CuentaPage";
import { cuenta, movimiento, respuestaJson } from "./testing";
import type { Cuenta } from "./tipos";

interface Mundo {
  cuenta: Cuenta;
  caja: EstadoCaja | "falla";
  forzadas?: Record<string, Response>;
}

const PENDIENTE = { presupuesto_id: 31, total: "1000.00", pendiente: "1000.00" };

function cuentaConDeuda(): Cuenta {
  return cuenta({
    saldo: "1000.00",
    movimientos: [movimiento({ id: 1, monto: "1000.00" })],
    pendientes: [PENDIENTE],
  });
}

function cuentaConPago(parcial: Partial<Cuenta> = {}): Cuenta {
  return cuenta({
    saldo: "600.00",
    movimientos: [
      movimiento({ id: 2, tipo: "pago", monto: "-400.00", concepto: "Recibo 1", recibo_id: 51 }),
      movimiento({ id: 1, monto: "1000.00" }),
    ],
    pendientes: [{ ...PENDIENTE, pendiente: "600.00" }],
    ...parcial,
  });
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    const forzada = mundo.forzadas?.[`${metodo} ${ruta}`];
    if (forzada !== undefined) return Promise.resolve(forzada.clone());
    if (ruta === "/cuentas/3" && metodo === "GET") return Promise.resolve(respuestaJson(mundo.cuenta));
    if (ruta === "/caja" && metodo === "GET") {
      return Promise.resolve(
        mundo.caja === "falla" ? respuestaJson({ detail: "error" }, 500) : respuestaJson(mundo.caja),
      );
    }
    if (ruta === "/caja/cobrar" && metodo === "POST") {
      mundo.cuenta = cuentaConPago();
      return Promise.resolve(respuestaJson(cobro({ numero: 1, monto: "400.00" }), 201));
    }
    if (/^\/recibos\/\d+\/anular$/.test(ruta) && metodo === "POST") {
      mundo.cuenta = cuentaConDeuda();
      return Promise.resolve(respuestaJson(recibo({ id: 51, anulado: true, motivo_anulacion: "x" })));
    }
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function montar(rol: "secretaria" | "admin"): void {
  render(<CuentaPage pacienteId={3} pacienteNombre="Ana Ficticia" rol={rol} alVolver={vi.fn()} />);
}

const llamadas = (fetchMock: ReturnType<typeof vi.fn>, metodo: string, ruta: string): number =>
  fetchMock.mock.calls.filter(
    (c) => String(c[0]).endsWith(ruta) && ((c[1] as RequestInit | undefined)?.method ?? "GET") === metodo,
  ).length;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CuentaPage: cobro (secretaria)", () => {
  it("ve Cobrar por cada presupuesto pendiente, con su importe", async () => {
    stubFetch({ cuenta: cuentaConDeuda(), caja: estadoCaja() });
    montar("secretaria");
    const lista = within(await screen.findByRole("list", { name: "Pendientes de cobro" }));
    expect(lista.getByText(/Presupuesto 31/)).toBeDefined();
    expect(lista.getByText(/Pendiente: \$ 1\.000,00/)).toBeDefined();
    const boton = screen.getByRole("button", { name: "Cobrar presupuesto 31" }) as HTMLButtonElement;
    expect(boton.disabled).toBe(false);
  });

  it("pide cuenta y caja a la vez al abrir", async () => {
    const fetchMock = stubFetch({ cuenta: cuentaConDeuda(), caja: estadoCaja() });
    montar("secretaria");
    await screen.findByRole("list", { name: "Pendientes de cobro" });
    expect(llamadas(fetchMock, "GET", "/cuentas/3")).toBe(1);
    expect(llamadas(fetchMock, "GET", "/caja")).toBe(1);
  });

  it("un cobro exitoso muestra el comprobante y refresca saldo y pendientes desde el servidor", async () => {
    const fetchMock = stubFetch({ cuenta: cuentaConDeuda(), caja: estadoCaja() });
    montar("secretaria");
    await userEvent.click(await screen.findByRole("button", { name: "Cobrar presupuesto 31" }));
    await userEvent.clear(screen.getByLabelText("Importe"));
    await userEvent.type(screen.getByLabelText("Importe"), "400.00");
    await userEvent.click(screen.getByRole("button", { name: "Cobrar" }));
    expect(await screen.findByRole("region", { name: "Comprobante" })).toBeDefined();
    expect(llamadas(fetchMock, "POST", "/caja/cobrar")).toBe(1);
    await userEvent.click(screen.getByRole("button", { name: "Listo" }));
    expect(screen.getByText(/Pendiente: \$ 600,00/)).toBeDefined();
    expect(screen.getByText(/debe/).textContent).toContain("$ 600,00");
  });

  it("con la caja bloqueada deshabilita Cobrar y lo dice con texto", async () => {
    stubFetch({
      cuenta: cuentaConDeuda(),
      caja: estadoCaja({ operable: false, bloqueo: "caja_pendiente" }),
    });
    montar("secretaria");
    const boton = (await screen.findByRole("button", { name: "Cobrar presupuesto 31" })) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    expect(screen.getByText(/cerrar la caja anterior/i)).toBeDefined();
  });

  it("con la caja de hoy cerrada tambien se deshabilita, con su propio texto", async () => {
    stubFetch({
      cuenta: cuentaConDeuda(),
      caja: estadoCaja({ operable: false, bloqueo: "caja_cerrada" }),
    });
    montar("secretaria");
    const boton = (await screen.findByRole("button", { name: "Cobrar presupuesto 31" })) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    expect(screen.getByText(/caja de hoy ya está cerrada/i)).toBeDefined();
  });

  it("si falla la consulta de caja, la cuenta se muestra y el servidor decide el cobro", async () => {
    stubFetch({
      cuenta: cuentaConDeuda(),
      caja: "falla",
      forzadas: { "POST /caja/cobrar": respuestaJson({ detail: "hay una caja anterior sin cerrar" }, 409) },
    });
    montar("secretaria");
    const boton = (await screen.findByRole("button", { name: "Cobrar presupuesto 31" })) as HTMLButtonElement;
    expect(screen.getByRole("status").textContent).toContain("El paciente debe");
    expect(boton.disabled).toBe(false);
    await userEvent.click(boton);
    await userEvent.click(screen.getByRole("button", { name: "Cobrar" }));
    expect((await screen.findByRole("alert")).textContent).toContain("hay una caja anterior sin cerrar");
  });

  it("sin pendientes no hay lista ni Cobrar", async () => {
    stubFetch({ cuenta: cuenta({ saldo: "0.00", movimientos: [] }), caja: estadoCaja() });
    montar("secretaria");
    await screen.findByText(/no tiene movimientos/i);
    expect(screen.queryByRole("list", { name: "Pendientes de cobro" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Cobrar presupuesto/ })).toBeNull();
  });

  it("cancelar el formulario no envia nada", async () => {
    const fetchMock = stubFetch({ cuenta: cuentaConDeuda(), caja: estadoCaja() });
    montar("secretaria");
    await userEvent.click(await screen.findByRole("button", { name: "Cobrar presupuesto 31" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog", { name: "Cobrar presupuesto" })).toBeNull();
    expect(llamadas(fetchMock, "POST", "/caja/cobrar")).toBe(0);
  });
});

describe("CuentaPage: admin", () => {
  it("no ve Cobrar ni consulta la caja", async () => {
    const fetchMock = stubFetch({ cuenta: cuentaConDeuda(), caja: estadoCaja() });
    montar("admin");
    await screen.findByRole("status");
    expect(screen.queryByRole("button", { name: /Cobrar/ })).toBeNull();
    expect(llamadas(fetchMock, "GET", "/caja")).toBe(0);
  });
});

describe("CuentaPage: anular recibo (admin)", () => {
  it("ve Anular recibo en un pago no anulado y no en uno anulado", async () => {
    const anulado = movimiento({ id: 3, tipo: "pago", monto: "-100.00", concepto: "Recibo 2", recibo_id: 52, anulado: true });
    stubFetch({
      cuenta: cuentaConPago({ movimientos: [anulado, ...cuentaConPago().movimientos] }),
      caja: estadoCaja(),
    });
    montar("admin");
    await screen.findByRole("list", { name: "Movimientos" });
    expect(screen.getAllByRole("button", { name: /Anular recibo/ })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Anular recibo 1" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Anular recibo 2" })).toBeNull();
  });

  it("la secretaria no tiene accion de anular recibo", async () => {
    stubFetch({ cuenta: cuentaConPago(), caja: estadoCaja() });
    montar("secretaria");
    await screen.findByRole("list", { name: "Movimientos" });
    expect(screen.queryByRole("button", { name: /Anular recibo/ })).toBeNull();
  });

  it("un motivo vacio no se envia", async () => {
    const fetchMock = stubFetch({ cuenta: cuentaConPago(), caja: estadoCaja() });
    montar("admin");
    await userEvent.click(await screen.findByRole("button", { name: "Anular recibo 1" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    expect(await screen.findByText("El motivo es obligatorio.")).toBeDefined();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes("/anular"))).toBe(false);
  });

  it("al anular con motivo, refresca la cuenta desde el servidor", async () => {
    const fetchMock = stubFetch({ cuenta: cuentaConPago(), caja: estadoCaja() });
    montar("admin");
    await userEvent.click(await screen.findByRole("button", { name: "Anular recibo 1" }));
    await userEvent.type(screen.getByLabelText("Motivo de la anulación"), "cobro duplicado");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    expect((await screen.findByRole("status")).textContent).toContain("$ 1.000,00");
    const anulacion = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/recibos/51/anular"));
    expect(JSON.parse(String((anulacion?.[1] as RequestInit).body))).toEqual({ motivo: "cobro duplicado" });
    expect(String(anulacion?.[0])).not.toContain("duplicado");
    expect(screen.queryByLabelText("Motivo de la anulación")).toBeNull();
  });

  it("un 409 del servidor queda visible", async () => {
    stubFetch({
      cuenta: cuentaConPago(),
      caja: estadoCaja(),
      forzadas: { "POST /recibos/51/anular": respuestaJson({ detail: "hay una caja anterior sin cerrar" }, 409) },
    });
    montar("admin");
    await userEvent.click(await screen.findByRole("button", { name: "Anular recibo 1" }));
    await userEvent.type(screen.getByLabelText("Motivo de la anulación"), "error");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    expect((await screen.findByRole("alert")).textContent).toContain("hay una caja anterior sin cerrar");
  });
});
