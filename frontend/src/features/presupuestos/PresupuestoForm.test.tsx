import { render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import { hallazgo } from "../odontograma/testing";
import { PresupuestoForm } from "./PresupuestoForm";
import { presupuesto, TRATAMIENTOS } from "./testing";

const NOMBRES = { caries: "Caries", ausente: "Ausente" };

const ACTIVO_1 = hallazgo({ id: 11, pieza_fdi: 16, cara: "oclusal", estado: "caries" });
const ACTIVO_2 = hallazgo({ id: 12, pieza_fdi: 36, cara: "pieza_completa", estado: "ausente" });
const ANULADO = hallazgo({ id: 13, pieza_fdi: 26, cara: "mesial", estado: "caries", deleted_at: "2026-10-20T10:00:00Z", motivo_baja: "error" });

function montar(props: Partial<ComponentProps<typeof PresupuestoForm>> = {}) {
  const alEnviar = vi.fn().mockResolvedValue(presupuesto({ total: "156000.00" }));
  render(
    <PresupuestoForm
      idBase="nuevo"
      hallazgos={[ACTIVO_1, ACTIVO_2, ANULADO]}
      nombres={NOMBRES}
      tratamientos={TRATAMIENTOS}
      etiquetaBoton="Guardar presupuesto"
      alEnviar={alEnviar}
      {...props}
    />,
  );
  return alEnviar;
}

describe("PresupuestoForm", () => {
  it("solo ofrece hallazgos activos, indicados por pieza y cara", async () => {
    montar();
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    const select = screen.getByLabelText(/Hallazgo/);
    const opciones = within(select).getAllByRole("option").map((o) => o.textContent);
    expect(opciones).toEqual(["Pieza 16 · Oclusal · Caries", "Pieza 36 · Pieza completa · Ausente"]);
    expect(opciones.join(" ")).not.toContain("Pieza 26");
  });

  it("sin ítems no envía", async () => {
    const alEnviar = montar();
    expect((screen.getByRole("button", { name: "Guardar presupuesto" }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    expect(alEnviar).not.toHaveBeenCalled();
    expect(screen.getByText(/Agregá al menos un ítem/)).toBeTruthy();
  });

  it("envía solo hallazgo, tratamiento y cantidad (sin precio ni total)", async () => {
    const alEnviar = montar();
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    await userEvent.selectOptions(screen.getByLabelText(/Tratamiento/), "2");
    await userEvent.clear(screen.getByLabelText(/Cantidad/));
    await userEvent.type(screen.getByLabelText(/Cantidad/), "3");
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    expect(alEnviar).toHaveBeenCalledWith([{ hallazgo_id: 11, tratamiento_id: 2, cantidad: 3 }]);
  });

  it("total del servidor tras guardar, sin sumar en el cliente", async () => {
    montar();
    expect(screen.getByText(/lo calcula el servidor/i)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    const hallazgos = screen.getAllByLabelText(/Hallazgo/);
    await userEvent.selectOptions(hallazgos[1] as HTMLElement, "12");
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    const total = await screen.findByRole("status");
    // 156000.00 es lo que dijo el servidor; ninguna suma de precios del catalogo coincide.
    expect(total.textContent).toContain("$ 156.000,00");
  });

  it("muestra error de API y deja el formulario editable", async () => {
    const alEnviar = vi.fn().mockRejectedValue(new ApiError(422, "hallazgo inválido para el paciente"));
    montar({ alEnviar });
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    expect((await screen.findByRole("alert")).textContent).toContain("hallazgo inválido para el paciente");
    expect((screen.getByRole("button", { name: "Guardar presupuesto" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("un error que no es de la API da un mensaje generico, sin datos", async () => {
    montar({ alEnviar: vi.fn().mockRejectedValue(new Error("detalle interno sensible")) });
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).not.toContain("sensible");
  });

  it("no deja repetir el mismo hallazgo con el mismo tratamiento", async () => {
    const alEnviar = montar();
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    expect(screen.getByText(/ítems repetidos/i)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Guardar presupuesto" }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.selectOptions(screen.getAllByLabelText(/Tratamiento/)[1] as HTMLElement, "3");
    expect(screen.queryByText(/ítems repetidos/i)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    expect(alEnviar).toHaveBeenCalledTimes(1);
  });

  it("quitar un ítem lo elimina del envio", async () => {
    const alEnviar = montar();
    await userEvent.click(screen.getByRole("button", { name: "Agregar ítem" }));
    await userEvent.click(screen.getByRole("button", { name: "Quitar ítem 1" }));
    expect((screen.getByRole("button", { name: "Guardar presupuesto" }) as HTMLButtonElement).disabled).toBe(true);
    expect(alEnviar).not.toHaveBeenCalled();
  });

  it("en edicion parte de los ítems actuales y marca el hallazgo que ya no es vigente", async () => {
    const alEnviar = montar({
      inicial: [
        { hallazgo_id: 11, tratamiento_id: 2, cantidad: 2 },
        { hallazgo_id: 99, tratamiento_id: 1, cantidad: 1 },
      ],
    });
    expect(screen.getAllByLabelText(/Hallazgo/)).toHaveLength(2);
    expect(screen.getByText(/ya no está vigente/i)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Guardar presupuesto" }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Quitar ítem 2" }));
    await userEvent.click(screen.getByRole("button", { name: "Guardar presupuesto" }));
    expect(alEnviar).toHaveBeenCalledWith([{ hallazgo_id: 11, tratamiento_id: 2, cantidad: 2 }]);
  });
});
