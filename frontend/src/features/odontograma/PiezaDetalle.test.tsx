import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api-client";
import { PiezaDetalle } from "./PiezaDetalle";
import { CATALOGO, hallazgo } from "./testing";
import type { Hallazgo } from "./tipos";

const NOMBRES = Object.fromEntries(CATALOGO.estados.map((e) => [e.codigo, e.nombre]));

interface Opciones {
  pieza?: number;
  hallazgos?: Hallazgo[];
  rol?: "odontologo" | "secretaria";
  alRegistrar?: ReturnType<typeof vi.fn>;
  alCorregir?: ReturnType<typeof vi.fn>;
  alBaja?: ReturnType<typeof vi.fn>;
}

function montar(op: Opciones = {}): void {
  render(
    <PiezaDetalle
      pieza={op.pieza ?? 16}
      hallazgos={op.hallazgos ?? []}
      catalogo={CATALOGO}
      nombres={NOMBRES}
      rol={op.rol ?? "odontologo"}
      alRegistrar={op.alRegistrar ?? vi.fn().mockResolvedValue(undefined)}
      alCorregir={op.alCorregir ?? vi.fn().mockResolvedValue(undefined)}
      alBaja={op.alBaja ?? vi.fn().mockResolvedValue(undefined)}
      alCerrar={vi.fn()}
    />,
  );
}

describe("PiezaDetalle: historial", () => {
  it("lista el mas reciente primero aunque lleguen desordenados", () => {
    montar({
      hallazgos: [
        hallazgo({ estado: "caries", fecha: "2026-10-01T10:00:00Z" }),
        hallazgo({ estado: "obturacion", fecha: "2026-10-20T10:00:00Z" }),
        hallazgo({ estado: "sano", fecha: "2026-10-10T10:00:00Z" }),
      ],
    });
    const items = within(screen.getByRole("list", { name: /historial de la pieza 16/i })).getAllByRole("listitem");
    expect(items.map((li) => li.querySelector(".titulo")?.textContent)).toEqual([
      "Obturación · Oclusal",
      "Sano · Oclusal",
      "Caries · Oclusal",
    ]);
  });

  it("muestra el motivo de un hallazgo dado de baja", () => {
    montar({
      hallazgos: [
        hallazgo({ estado: "caries", deleted_at: "2026-10-12T10:00:00Z", motivo_baja: "cargado por error" }),
      ],
    });
    const item = within(screen.getByRole("list", { name: /historial/i })).getAllByRole("listitem")[0] as HTMLElement;
    expect(item.getAttribute("data-anulado")).toBe("true");
    expect(item.textContent).toContain("Dado de baja");
    expect(item.textContent).toContain("cargado por error");
  });

  it("sin hallazgos dice que la pieza no tiene registros", () => {
    montar({ hallazgos: [] });
    expect(screen.getByText(/sin registros/i)).toBeDefined();
  });

  it("ignora los hallazgos de otras piezas", () => {
    montar({ rol: "secretaria", hallazgos: [hallazgo({ pieza_fdi: 26, estado: "ausente", cara: "pieza_completa" })] });
    expect(screen.queryByText(/ausente/i)).toBeNull();
    expect(screen.getByText(/sin registros/i)).toBeDefined();
  });
});

describe("PiezaDetalle: permisos", () => {
  it("la secretaria ve el historial sin controles de alta, correccion ni baja", () => {
    montar({ rol: "secretaria", hallazgos: [hallazgo({ es_propio: true })] });
    expect(screen.getByRole("list", { name: /historial/i })).toBeDefined();
    expect(screen.queryByRole("button", { name: /registrar/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /corregir/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /dar de baja/i })).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("el odontologo ve corregir y baja solo en hallazgos propios y activos", () => {
    montar({
      hallazgos: [
        hallazgo({ id: 1, es_propio: true, estado: "caries" }),
        hallazgo({ id: 2, es_propio: false, estado: "sano", cara: "mesial" }),
        hallazgo({ id: 3, es_propio: true, estado: "sano", cara: "distal", deleted_at: "2026-10-12T10:00:00Z", motivo_baja: "x" }),
      ],
    });
    expect(screen.getAllByRole("button", { name: /^corregir/i })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /^dar de baja/i })).toHaveLength(1);
    expect(screen.getByRole("button", { name: /registrar hallazgo/i })).toBeDefined();
  });
});

describe("PiezaDetalle: formulario de alta", () => {
  it("en una pieza inferior no ofrece palatina y con ausente solo ofrece pieza completa", async () => {
    const usuario = userEvent.setup();
    montar({ pieza: 36 });
    const cara = screen.getByLabelText("Cara") as HTMLSelectElement;
    const opciones = (): string[] => Array.from(cara.options).map((o) => o.value);
    expect(opciones()).not.toContain("palatina");
    expect(opciones()).toContain("lingual");
    await usuario.selectOptions(screen.getByLabelText("Estado"), "ausente");
    expect(opciones()).toEqual(["pieza_completa"]);
    await usuario.selectOptions(screen.getByLabelText("Estado"), "caries");
    expect(opciones()).toContain("oclusal");
  });

  it("en una pieza superior ofrece palatina y no lingual", () => {
    montar({ pieza: 16 });
    const valores = Array.from((screen.getByLabelText("Cara") as HTMLSelectElement).options).map((o) => o.value);
    expect(valores).toContain("palatina");
    expect(valores).not.toContain("lingual");
  });

  it("registra con pieza, cara y estado elegidos", async () => {
    const usuario = userEvent.setup();
    const alRegistrar = vi.fn().mockResolvedValue(undefined);
    montar({ pieza: 16, alRegistrar });
    await usuario.selectOptions(screen.getByLabelText("Estado"), "obturacion");
    await usuario.selectOptions(screen.getByLabelText("Cara"), "mesial");
    await usuario.click(screen.getByRole("button", { name: /registrar hallazgo/i }));
    expect(alRegistrar).toHaveBeenCalledWith({ pieza_fdi: 16, cara: "mesial", estado: "obturacion" });
  });

  it("muestra el error de la API con role=alert", async () => {
    const usuario = userEvent.setup();
    const alRegistrar = vi.fn().mockRejectedValue(new ApiError(403, "sin turno vigente con el paciente"));
    montar({ alRegistrar });
    await usuario.click(screen.getByRole("button", { name: /registrar hallazgo/i }));
    expect((await screen.findByRole("alert")).textContent).toContain("sin turno vigente con el paciente");
  });
});

describe("PiezaDetalle: correccion y baja", () => {
  it("corrige exigiendo motivo y manda los datos nuevos", async () => {
    const usuario = userEvent.setup();
    const alCorregir = vi.fn().mockResolvedValue(undefined);
    montar({ hallazgos: [hallazgo({ id: 9, estado: "caries", cara: "oclusal" })], alCorregir });
    await usuario.click(screen.getByRole("button", { name: /^corregir/i }));
    const enviar = screen.getByRole("button", { name: /guardar corrección/i });
    expect((enviar as HTMLButtonElement).disabled).toBe(true);
    await usuario.selectOptions(screen.getByLabelText("Estado", { selector: "#corregir-9-estado" }), "obturacion");
    await usuario.type(screen.getByLabelText(/motivo de la corrección/i), "era una obturación");
    await usuario.click(enviar);
    expect(alCorregir).toHaveBeenCalledWith(9, { pieza_fdi: 16, cara: "oclusal", estado: "obturacion" }, "era una obturación");
  });

  it("da de baja con motivo obligatorio", async () => {
    const usuario = userEvent.setup();
    const alBaja = vi.fn().mockResolvedValue(undefined);
    montar({ hallazgos: [hallazgo({ id: 5 })], alBaja });
    await usuario.click(screen.getByRole("button", { name: /^dar de baja/i }));
    const confirmar = screen.getByRole("button", { name: /confirmar baja/i });
    expect((confirmar as HTMLButtonElement).disabled).toBe(true);
    await usuario.type(screen.getByLabelText(/motivo de la baja/i), "cargado por error");
    await usuario.click(confirmar);
    expect(alBaja).toHaveBeenCalledWith(5, "cargado por error");
  });

  it("un 409 de baja se muestra como alerta", async () => {
    const usuario = userEvent.setup();
    const alBaja = vi.fn().mockRejectedValue(new ApiError(409, "el hallazgo ya está dado de baja"));
    montar({ hallazgos: [hallazgo({ id: 5 })], alBaja });
    await usuario.click(screen.getByRole("button", { name: /^dar de baja/i }));
    await usuario.type(screen.getByLabelText(/motivo de la baja/i), "otra vez");
    await usuario.click(screen.getByRole("button", { name: /confirmar baja/i }));
    expect((await screen.findByRole("alert")).textContent).toContain("ya está dado de baja");
  });
});
