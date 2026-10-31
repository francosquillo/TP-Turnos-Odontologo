import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import { RecibosLista } from "./RecibosLista";
import { recibo } from "./testing";

const ANULADO = recibo({
  id: 50, numero: 1, monto: "250.50", medio: "transferencia", anulado: true,
  motivo_anulacion: "cobro duplicado", anulado_por: 1, anulado_at: "2026-10-31T16:00:00Z",
});
const VIGENTE = recibo({ id: 51, numero: 2, monto: "400.00", medio: "tarjeta_simulada" });

function montar(rol: "secretaria" | "admin", alAnular = vi.fn().mockResolvedValue(undefined)) {
  render(<RecibosLista recibos={[VIGENTE, ANULADO]} rol={rol} alAnular={alAnular} />);
  return { alAnular };
}

describe("RecibosLista", () => {
  it("lista numero, paciente, importe y medio; el anulado lo dice con texto y muestra el motivo", () => {
    montar("secretaria");
    const items = within(screen.getByRole("list", { name: "Recibos del día" })).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toContain("Recibo N° 2");
    expect(items[0]?.textContent).toContain("Ana Ficticia");
    expect(items[0]?.textContent).toContain("$ 400,00");
    expect(items[0]?.textContent).toContain("Tarjeta (simulada)");
    expect(items[0]?.textContent).not.toMatch(/Anulado/);
    expect(items[1]?.textContent).toContain("Recibo N° 1");
    expect(items[1]?.textContent).toContain("Anulado");
    expect(items[1]?.textContent).toContain("cobro duplicado");
    expect(items[1]?.textContent).toContain("$ 250,50");
  });

  it("sin recibos lo dice con texto", () => {
    render(<RecibosLista recibos={[]} rol="admin" alAnular={vi.fn()} />);
    expect(screen.getByText(/No hay recibos/i)).toBeDefined();
    expect(screen.queryByRole("list", { name: "Recibos del día" })).toBeNull();
  });

  it("la secretaria no tiene accion de anular", () => {
    montar("secretaria");
    expect(screen.queryByRole("button", { name: /Anular/ })).toBeNull();
  });

  it("el admin ve Anular solo en los recibos no anulados", () => {
    montar("admin");
    expect(screen.getAllByRole("button", { name: /Anular recibo/ })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Anular recibo 2" })).toBeDefined();
  });

  it("anular con motivo: lo envia en el recibo correcto", async () => {
    const { alAnular } = montar("admin");
    await userEvent.click(screen.getByRole("button", { name: "Anular recibo 2" }));
    await userEvent.type(screen.getByLabelText("Motivo de la anulación"), "cobro duplicado");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    expect(alAnular).toHaveBeenCalledWith(51, "cobro duplicado");
  });

  it("un motivo vacio no se envia y se indica que es obligatorio", async () => {
    const { alAnular } = montar("admin");
    await userEvent.click(screen.getByRole("button", { name: "Anular recibo 2" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    expect(alAnular).not.toHaveBeenCalled();
    expect((await screen.findByText("El motivo es obligatorio.")).textContent).toBeTruthy();
  });

  it("un 409 del servidor queda visible y el formulario sigue abierto", async () => {
    const alAnular = vi.fn().mockRejectedValue(new ApiError(409, "hay una caja anterior sin cerrar"));
    montar("admin", alAnular);
    await userEvent.click(screen.getByRole("button", { name: "Anular recibo 2" }));
    await userEvent.type(screen.getByLabelText("Motivo de la anulación"), "error");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
    expect((await screen.findByRole("alert")).textContent).toContain("hay una caja anterior sin cerrar");
    expect(screen.getByLabelText("Motivo de la anulación")).toBeDefined();
  });

  it("cancelar cierra el formulario sin enviar", async () => {
    const { alAnular } = montar("admin");
    await userEvent.click(screen.getByRole("button", { name: "Anular recibo 2" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByLabelText("Motivo de la anulación")).toBeNull();
    expect(alAnular).not.toHaveBeenCalled();
  });
});
