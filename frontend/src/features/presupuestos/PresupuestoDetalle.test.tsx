import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PresupuestoDetalle } from "./PresupuestoDetalle";
import { item, presupuesto } from "./testing";

describe("PresupuestoDetalle", () => {
  it("el estado se muestra con texto, no solo con color", () => {
    render(<PresupuestoDetalle presupuesto={presupuesto({ estado: "presentado" })} />);
    const estado = screen.getByLabelText("Estado del presupuesto");
    expect(estado.textContent).toBe("Presentado");
    expect(estado.getAttribute("data-pres")).toBe("presentado");
  });

  it("muestra pieza, cara, tratamiento, cantidad, precio, subtotal y total con formato es-AR", () => {
    render(<PresupuestoDetalle presupuesto={presupuesto({ total: "36000.00" })} />);
    const fila = screen.getAllByRole("listitem")[0] as HTMLElement;
    expect(fila.textContent).toContain("Pieza 16 · Oclusal");
    expect(fila.textContent).toContain("Obturación simple");
    expect(fila.textContent).toContain("2 × $ 18.000,00");
    expect(fila.textContent).toContain("$ 36.000,00");
    expect(screen.getByText(/Total/).textContent).toContain("$ 36.000,00");
  });

  it("hallazgo no vigente visible con texto", () => {
    render(
      <PresupuestoDetalle
        presupuesto={presupuesto({ estado: "aceptado", items: [item({ hallazgo_vigente: false })] })}
      />,
    );
    expect(screen.getByText(/ya no está vigente/i)).toBeTruthy();
  });

  it("un hallazgo vigente no muestra el aviso", () => {
    render(<PresupuestoDetalle presupuesto={presupuesto()} />);
    expect(screen.queryByText(/ya no está vigente/i)).toBeNull();
  });

  it("admin sin pieza: la vista financiera no inventa datos clinicos", () => {
    render(
      <PresupuestoDetalle
        presupuesto={presupuesto({
          estado: "rechazado",
          motivo_rechazo: null,
          items: [item({ pieza_fdi: null, cara: null })],
        })}
      />,
    );
    const fila = screen.getAllByRole("listitem")[0] as HTMLElement;
    expect(fila.textContent).not.toMatch(/Pieza|null|undefined/);
    expect(fila.textContent).toContain("Obturación simple");
    expect(screen.queryByText(/Motivo del rechazo/)).toBeNull();
  });

  it("rechazado muestra el motivo cuando existe", () => {
    render(<PresupuestoDetalle presupuesto={presupuesto({ estado: "rechazado", motivo_rechazo: "Muy caro" })} />);
    expect(screen.getByText(/Motivo del rechazo/).textContent).toContain("Muy caro");
  });

  it("cargo anulado visible con texto y el estado sigue siendo aceptado", () => {
    render(<PresupuestoDetalle presupuesto={presupuesto({ estado: "aceptado", cargo_anulado: true })} />);
    expect(screen.getByLabelText("Estado del presupuesto").textContent).toBe("Aceptado");
    expect(screen.getByText(/Cargo anulado/i)).toBeTruthy();
  });

  it("lista cada ítem en su propio renglon", () => {
    render(
      <PresupuestoDetalle
        presupuesto={presupuesto({
          items: [item({ tratamiento_nombre: "A" }), item({ tratamiento_nombre: "B", pieza_fdi: 36, cara: "pieza_completa" })],
        })}
      />,
    );
    const lista = screen.getByRole("list", { name: /Ítems/ });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(2);
  });
});
