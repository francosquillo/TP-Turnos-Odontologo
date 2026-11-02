import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { consultarCaja } from "./api";
import { CajaPage } from "./CajaPage";
import { IngresosLiquidacion } from "./IngresosLiquidacion";
import { estadoCaja, ingresoLiquidacion, respuestaJson } from "./testing";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api de caja: ingresos de liquidacion (C-11, D-15)", () => {
  it("consultarCaja conserva los ingresos con su signo y el importe como texto", async () => {
    const dato = estadoCaja({
      ingresos_liquidacion: [
        ingresoLiquidacion({ monto: "10500.00" }),
        ingresoLiquidacion({ liquidacion_id: 4, monto: "-10500.00" }),
      ],
    });
    const leido = await consultarCaja(undefined, vi.fn().mockResolvedValue(respuestaJson(dato)));
    expect(leido.ingresos_liquidacion.map((i) => i.monto)).toEqual(["10500.00", "-10500.00"]);
    expect(typeof leido.ingresos_liquidacion[0]?.monto).toBe("string");
  });

  it.each([
    ["sin el campo", (() => { const { ingresos_liquidacion: _omitido, ...resto } = estadoCaja(); return resto; })()],
    ["no es una lista", { ...estadoCaja(), ingresos_liquidacion: {} }],
    ["importe numerico", { ...estadoCaja(), ingresos_liquidacion: [{ ...ingresoLiquidacion(), monto: 10500 }] }],
    ["medio desconocido", { ...estadoCaja(), ingresos_liquidacion: [{ ...ingresoLiquidacion(), medio: "cheque" }] }],
    ["sin obra social", { ...estadoCaja(), ingresos_liquidacion: [{ ...ingresoLiquidacion(), obra_social: null }] }],
  ])("forma inesperada: %s", async (_nombre, cuerpo) => {
    await expect(
      consultarCaja(undefined, vi.fn().mockResolvedValue(respuestaJson(cuerpo))),
    ).rejects.toMatchObject({ message: expect.stringContaining("forma inesperada") });
  });
});

describe("IngresosLiquidacion", () => {
  it("lista aparte cada ingreso con obra social, periodo, medio e importe", () => {
    render(
      <IngresosLiquidacion
        ingresos={[
          ingresoLiquidacion({ obra_social: "OS Ficticia Demo", periodo: "2026-10-01", medio: "transferencia", monto: "10500.00" }),
          ingresoLiquidacion({ liquidacion_id: 4, obra_social: "OS Ficticia Demo", periodo: "2026-10-01", medio: "transferencia", monto: "-10500.00" }),
        ]}
      />,
    );
    const filas = within(screen.getByRole("list", { name: "Ingresos de obras sociales" })).getAllByRole("listitem");
    expect(filas).toHaveLength(2);
    expect(filas[0]?.textContent).toContain("OS Ficticia Demo");
    expect(filas[0]?.textContent).toContain("10/2026");
    expect(filas[0]?.textContent).toContain("Transferencia");
    expect(filas[0]?.textContent).toContain("$ 10.500,00");
    expect(filas[1]?.textContent).toContain("-$ 10.500,00");
    expect(filas[1]?.textContent).toMatch(/Reversión/);
  });

  it("un dia sin ingresos lo dice con texto", () => {
    render(<IngresosLiquidacion ingresos={[]} />);
    expect(screen.getByText(/Sin ingresos de obras sociales/)).toBeDefined();
    expect(screen.queryByRole("list", { name: "Ingresos de obras sociales" })).toBeNull();
  });
});

describe("CajaPage con ingresos de liquidacion", () => {
  function stub(estado: ReturnType<typeof estadoCaja>): void {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: unknown) => {
        const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
        if (ruta.startsWith("/recibos")) return Promise.resolve(respuestaJson([]));
        return Promise.resolve(respuestaJson(estado));
      }),
    );
  }

  it("muestra los ingresos de la OS separados de los recibos, tambien para el admin", async () => {
    stub(estadoCaja({ ingresos_liquidacion: [ingresoLiquidacion()] }));
    render(<CajaPage rol="admin" />);
    expect(await screen.findByRole("list", { name: "Ingresos de obras sociales" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Recibos del día" })).toBeDefined();
  });

  it("un dia sin ingresos de OS lo indica", async () => {
    stub(estadoCaja());
    render(<CajaPage rol="secretaria" />);
    expect(await screen.findByText(/Sin ingresos de obras sociales/)).toBeDefined();
  });
});
