import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CobroModal } from "./CobroModal";
import { cobro, respuestaJson } from "./testing";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

interface Montado {
  alCobrado: ReturnType<typeof vi.fn>;
  alCerrar: ReturnType<typeof vi.fn>;
  desmontar: () => void;
}

function montar(fetchMock: ReturnType<typeof vi.fn>, pendiente = "600.00"): Montado {
  vi.stubGlobal("fetch", fetchMock);
  const alCobrado = vi.fn();
  const alCerrar = vi.fn();
  const { unmount } = render(
    <CobroModal presupuestoId={31} pendiente={pendiente} alCobrado={alCobrado} alCerrar={alCerrar} />,
  );
  return { alCobrado, alCerrar, desmontar: unmount };
}

const cuerpo = (fetchMock: ReturnType<typeof vi.fn>, n = 0): Record<string, unknown> =>
  JSON.parse(String((fetchMock.mock.calls[n]?.[1] as RequestInit).body)) as Record<string, unknown>;

async function cargarImporte(texto: string): Promise<void> {
  const campo = screen.getByLabelText("Importe");
  await userEvent.clear(campo);
  if (texto !== "") await userEvent.type(campo, texto);
}

const cobrarBoton = (): HTMLButtonElement => screen.getByRole("button", { name: "Cobrar" });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CobroModal", () => {
  it.each(["", "abc", "0", "0.00", "-5", "10.123", "1,5"])("el importe invalido %j no se envia", async (texto) => {
    const fetchMock = vi.fn();
    montar(fetchMock);
    await cargarImporte(texto);
    await userEvent.click(cobrarBoton());
    expect(fetchMock).not.toHaveBeenCalled();
    expect((await screen.findByRole("alert")).textContent).toMatch(/importe/i);
  });

  it("el importe viaja como texto (sin number) junto con el medio elegido", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(cobro(), 201));
    montar(fetchMock);
    await cargarImporte("400.5");
    await userEvent.click(screen.getByLabelText("Transferencia"));
    await userEvent.click(cobrarBoton());
    const enviado = cuerpo(fetchMock);
    expect(enviado["monto"]).toBe("400.5");
    expect(typeof enviado["monto"]).toBe("string");
    expect(enviado["medio"]).toBe("transferencia");
    expect(enviado["presupuesto_id"]).toBe(31);
    expect(Object.keys(enviado).sort()).toEqual(["clave_idempotencia", "medio", "monto", "presupuesto_id"]);
  });

  it("ofrece exactamente los tres medios simulados y efectivo viene elegido", () => {
    montar(vi.fn());
    const radios = screen.getAllByRole("radio").map((r) => (r as HTMLInputElement).value);
    expect(radios).toEqual(["efectivo", "transferencia", "tarjeta_simulada"]);
    expect((screen.getByLabelText("Efectivo") as HTMLInputElement).checked).toBe(true);
    expect(screen.getByLabelText("Tarjeta (simulada)")).toBeDefined();
  });

  it("el boton se deshabilita mientras envia y no hay doble envio", async () => {
    let resolver: (r: Response) => void = () => undefined;
    const fetchMock = vi.fn().mockReturnValue(new Promise<Response>((res) => { resolver = res; }));
    montar(fetchMock);
    const boton = cobrarBoton();
    await userEvent.click(boton);
    expect(boton.disabled).toBe(true);
    await userEvent.click(boton);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolver(respuestaJson(cobro(), 201));
    });
  });

  it.each([
    [422, "el importe supera el pendiente"],
    [409, "hay una caja anterior sin cerrar"],
  ])("un %i del servidor queda visible", async (status, detalle) => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson({ detail: detalle }, status));
    const { alCobrado } = montar(fetchMock);
    await userEvent.click(cobrarBoton());
    expect((await screen.findByRole("alert")).textContent).toContain(detalle);
    expect(alCobrado).not.toHaveBeenCalled();
  });

  it("al cobrar muestra el comprobante con el numero y la leyenda de pago simulado", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      respuestaJson(cobro({ numero: 12, monto: "400.00", medio: "tarjeta_simulada", fecha: "2026-10-31" }), 201),
    );
    const { alCobrado } = montar(fetchMock);
    await userEvent.click(cobrarBoton());
    const comprobante = await screen.findByRole("region", { name: "Comprobante" });
    expect(comprobante.textContent).toContain("12");
    expect(comprobante.textContent).toContain("Ana Ficticia");
    expect(comprobante.textContent).toContain("$ 400,00");
    expect(comprobante.textContent).toContain("Tarjeta (simulada)");
    expect(comprobante.textContent).toContain("31/10/2026");
    expect(comprobante.textContent).toMatch(/Pago simulado, sin validez fiscal/);
    expect(alCobrado).toHaveBeenCalledTimes(1);
  });
});

describe("CobroModal: clave de idempotencia (D-25)", () => {
  it("genera una clave UUID v4 por apertura y la envia en el cuerpo", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(cobro(), 201));
    montar(fetchMock);
    await userEvent.click(cobrarBoton());
    expect(String(cuerpo(fetchMock)["clave_idempotencia"])).toMatch(UUID_V4);
  });

  it("tras un fallo de red reintenta con la MISMA clave", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(respuestaJson(cobro(), 200));
    montar(fetchMock);
    await userEvent.click(cobrarBoton());
    await userEvent.click(await screen.findByRole("button", { name: "Reintentar" }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(cuerpo(fetchMock, 1)["clave_idempotencia"]).toBe(cuerpo(fetchMock, 0)["clave_idempotencia"]);
    expect(await screen.findByRole("region", { name: "Comprobante" })).toBeDefined();
  });

  it("tras un 500 reintenta con la misma clave", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respuestaJson({ detail: "error interno" }, 500))
      .mockResolvedValueOnce(respuestaJson(cobro(), 201));
    montar(fetchMock);
    await userEvent.click(cobrarBoton());
    await userEvent.click(await screen.findByRole("button", { name: "Reintentar" }));
    expect(cuerpo(fetchMock, 1)["clave_idempotencia"]).toBe(cuerpo(fetchMock, 0)["clave_idempotencia"]);
  });

  it("tras un resultado incierto congela importe y medio, y ofrece Reintentar o Cerrar", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    montar(fetchMock);
    await cargarImporte("250");
    await userEvent.click(screen.getByLabelText("Transferencia"));
    await userEvent.click(cobrarBoton());
    const aviso = await screen.findByRole("alert");
    expect(aviso.textContent).toMatch(/no sabemos si el cobro se registr/i);
    expect((screen.getByLabelText("Importe") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText("Importe") as HTMLInputElement).value).toBe("250");
    for (const radio of screen.getAllByRole("radio")) expect(radio.matches(":disabled")).toBe(true);
    expect(screen.queryByRole("button", { name: "Cobrar" })).toBeNull();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Cerrar" })).toBeDefined();
  });

  it("Cerrar tras un resultado incierto pide refrescar la cuenta", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const { alCerrar } = montar(fetchMock);
    await userEvent.click(cobrarBoton());
    await userEvent.click(await screen.findByRole("button", { name: "Cerrar" }));
    expect(alCerrar).toHaveBeenCalledWith(true);
  });

  it("un 4xx vuelve a habilitar los campos y conserva la clave", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respuestaJson({ detail: "el importe supera el pendiente" }, 422))
      .mockResolvedValueOnce(respuestaJson(cobro({ monto: "600.00" }), 201));
    montar(fetchMock);
    await cargarImporte("999");
    await userEvent.click(cobrarBoton());
    await screen.findByRole("alert");
    const importe = screen.getByLabelText("Importe") as HTMLInputElement;
    expect(importe.disabled).toBe(false);
    expect(importe.value).toBe("999");
    await cargarImporte("600");
    await userEvent.click(cobrarBoton());
    expect(cuerpo(fetchMock, 1)["monto"]).toBe("600");
    expect(cuerpo(fetchMock, 1)["clave_idempotencia"]).toBe(cuerpo(fetchMock, 0)["clave_idempotencia"]);
  });

  it("otra apertura del formulario genera otra clave", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(cobro(), 201));
    const primero = montar(fetchMock);
    await userEvent.click(cobrarBoton());
    await screen.findByRole("region", { name: "Comprobante" });
    primero.desmontar();
    montar(fetchMock);
    await userEvent.click(cobrarBoton());
    expect(cuerpo(fetchMock, 1)["clave_idempotencia"]).not.toBe(cuerpo(fetchMock, 0)["clave_idempotencia"]);
  });

  it("un 200 (reintento) muestra el comprobante igual que un 201", async () => {
    const original = cobro({ numero: 8 });
    const con201 = vi.fn().mockResolvedValue(respuestaJson(original, 201));
    const primero = montar(con201);
    await userEvent.click(cobrarBoton());
    const texto201 = (await screen.findByRole("region", { name: "Comprobante" })).textContent;
    primero.desmontar();
    const con200 = vi.fn().mockResolvedValue(respuestaJson(original, 200));
    montar(con200);
    await userEvent.click(cobrarBoton());
    expect((await screen.findByRole("region", { name: "Comprobante" })).textContent).toBe(texto201);
  });

  it("si el recibo devuelto esta anulado, lo indica con texto", async () => {
    const anulado = cobro({
      anulado: true, motivo_anulacion: "cobro duplicado", anulado_por: 1, anulado_at: "2026-10-31T16:00:00Z",
    });
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(anulado, 200));
    montar(fetchMock);
    await userEvent.click(cobrarBoton());
    const comprobante = await screen.findByRole("region", { name: "Comprobante" });
    expect(comprobante.textContent).toMatch(/Este recibo está anulado/);
    expect(comprobante.textContent).toContain("cobro duplicado");
  });
});
