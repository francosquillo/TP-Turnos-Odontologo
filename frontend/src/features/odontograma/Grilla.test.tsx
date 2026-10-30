import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Grilla } from "./Grilla";
import { hallazgo } from "./testing";

// vitest no entrega el contenido de un .css con `?raw`; `glob` con query sí.
const cssOdontograma: string = Object.values(
  import.meta.glob<string>("../../styles/odontograma.css", { query: "?raw", import: "default", eager: true }),
).join("\n");

const NOMBRES = { caries: "Caries", obturacion: "Obturación", ausente: "Ausente" };

describe("Grilla", () => {
  it("dibuja 32 botones con aria-label y sin las piezas inexistentes", () => {
    render(<Grilla hallazgos={[]} nombres={NOMBRES} seleccionada={null} alSeleccionar={vi.fn()} />);
    const botones = screen.getAllByRole("button", { name: /^Pieza \d\d/ });
    expect(botones).toHaveLength(32);
    for (const inexistente of [19, 20, 29, 30, 39, 40]) {
      expect(screen.queryByRole("button", { name: new RegExp(`^Pieza ${inexistente}\\b`) })).toBeNull();
    }
  });

  it("agrupa por cuadrante en orden clinico", () => {
    render(<Grilla hallazgos={[]} nombres={NOMBRES} seleccionada={null} alSeleccionar={vi.fn()} />);
    const numerosDe = (nombre: string): number[] =>
      within(screen.getByRole("group", { name: nombre }))
        .getAllByRole("button")
        .map((b) => Number(/^Pieza (\d\d)/.exec(b.getAttribute("aria-label") ?? "")?.[1]));
    expect(numerosDe("Superior derecho")).toEqual([18, 17, 16, 15, 14, 13, 12, 11]);
    expect(numerosDe("Superior izquierdo")).toEqual([21, 22, 23, 24, 25, 26, 27, 28]);
    expect(numerosDe("Inferior derecho")).toEqual([48, 47, 46, 45, 44, 43, 42, 41]);
    expect(numerosDe("Inferior izquierdo")).toEqual([31, 32, 33, 34, 35, 36, 37, 38]);
  });

  it("muestra el estado vigente en texto, no solo con color", () => {
    const hallazgos = [
      hallazgo({ pieza_fdi: 16, cara: "oclusal", estado: "caries", fecha: "2026-10-01T10:00:00Z" }),
      hallazgo({ pieza_fdi: 16, cara: "oclusal", estado: "obturacion", fecha: "2026-10-20T10:00:00Z" }),
      hallazgo({ pieza_fdi: 11, cara: "pieza_completa", estado: "ausente" }),
      hallazgo({ pieza_fdi: 26, cara: "mesial", estado: "caries", deleted_at: "2026-10-22T10:00:00Z", motivo_baja: "x" }),
    ];
    render(<Grilla hallazgos={hallazgos} nombres={NOMBRES} seleccionada={null} alSeleccionar={vi.fn()} />);
    const p16 = screen.getByRole("button", { name: /^Pieza 16/ });
    expect(p16.getAttribute("aria-label")).toBe("Pieza 16: Obturación (Oclusal)");
    expect(p16.textContent).toContain("Obturación");
    expect(p16.textContent).not.toContain("Caries");
    expect(screen.getByRole("button", { name: /^Pieza 11/ }).getAttribute("aria-label")).toBe(
      "Pieza 11: Ausente (Pieza completa)",
    );
    // dado de baja: la pieza queda sin registros activos; incisivo/canino rotulan Incisal
    expect(screen.getByRole("button", { name: /^Pieza 26/ }).getAttribute("aria-label")).toBe(
      "Pieza 26: sin registros",
    );
  });

  it("rotula Incisal en un incisivo y avisa la seleccion con aria-pressed", async () => {
    const alSeleccionar = vi.fn();
    render(
      <Grilla
        hallazgos={[hallazgo({ pieza_fdi: 12, cara: "oclusal", estado: "caries" })]}
        nombres={NOMBRES}
        seleccionada={12}
        alSeleccionar={alSeleccionar}
      />,
    );
    expect(screen.getByRole("button", { name: /^Pieza 12/ }).getAttribute("aria-label")).toBe(
      "Pieza 12: Caries (Incisal)",
    );
    expect(screen.getByRole("button", { name: /^Pieza 12/ }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /^Pieza 13/ }).getAttribute("aria-pressed")).toBe("false");
    await userEvent.click(screen.getByRole("button", { name: /^Pieza 13/ }));
    expect(alSeleccionar).toHaveBeenCalledWith(13);
  });
});

describe("odontograma.css", () => {
  it("usa solo variables de tokens: sin colores literales", () => {
    const sinComentarios = cssOdontograma.replace(/\/\*[\s\S]*?\*\//g, "");
    expect(sinComentarios).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(sinComentarios).not.toMatch(/\brgba?\(/);
    expect(sinComentarios).not.toMatch(/\bhsla?\(/);
    expect(sinComentarios).toMatch(/var\(--/);
  });

  it("define el objetivo tactil de 44 px y el foco con tokens", () => {
    expect(cssOdontograma).toMatch(/var\(--target-min\)/);
    expect(cssOdontograma).toMatch(/var\(--focus-ring\)/);
  });
});
