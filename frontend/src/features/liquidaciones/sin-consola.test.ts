import { describe, expect, it } from "vitest";

// Lee el codigo fuente de produccion del feature (sin tests ni fixtures).
const fuentes = import.meta.glob<string>(
  ["./*.ts", "./*.tsx", "!./*.test.ts", "!./*.test.tsx", "!./testing.ts"],
  { query: "?raw", import: "default", eager: true },
);

const css = import.meta.glob<string>("../../styles/liquidaciones.css", {
  query: "?raw",
  import: "default",
  eager: true,
});

describe("liquidaciones sin consola (C-11)", () => {
  it("encuentra los archivos de produccion del feature", () => {
    const nombres = Object.keys(fuentes).map((n) => n.replace("./", ""));
    expect(nombres).toEqual(
      expect.arrayContaining(["api.ts", "tipos.ts", "LiquidacionesPage.tsx", "LiquidacionDetalleVista.tsx", "GenerarForm.tsx"]),
    );
  });

  it("ningun archivo del feature usa console", () => {
    const culpables = Object.entries(fuentes)
      .filter(([, codigo]) => /\bconsole\s*\./.test(codigo))
      .map(([nombre]) => nombre);
    expect(culpables).toEqual([]);
  });

  it("sin `any` explicito en el codigo de produccion", () => {
    const culpables = Object.entries(fuentes)
      .filter(([, codigo]) => /:\s*any\b|<any>|\bas any\b/.test(codigo))
      .map(([nombre]) => nombre);
    expect(culpables).toEqual([]);
  });

  it("el importe nunca se convierte a number (sin aritmetica de dinero en el cliente)", () => {
    const culpables = Object.entries(fuentes)
      .filter(([, codigo]) => /parseFloat|Number\(\s*(monto|importe|total|subtotal)/.test(codigo))
      .map(([nombre]) => nombre);
    expect(culpables).toEqual([]);
  });

  it("el periodo y las fechas no se interpretan con Date (se corre un dia en UTC-3)", () => {
    const sinComentarios = (codigo: string): string =>
      codigo.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    const culpables = Object.entries(fuentes)
      .filter(([, codigo]) => /new Date\(/.test(sinComentarios(codigo)))
      .map(([nombre]) => nombre);
    expect(culpables).toEqual([]);
  });
});

describe("liquidaciones.css usa solo tokens del design system", () => {
  const [hoja] = Object.values(css);

  it("no tiene colores literales (hex, rgb, hsl)", () => {
    expect((hoja ?? "").length).toBeGreaterThan(100);
    const sinComentarios = (hoja ?? "").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(sinComentarios).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(sinComentarios).not.toMatch(/\b(rgb|rgba|hsl|hsla)\(/);
  });

  it("todo var(--x) existe en tokens.css", async () => {
    const usados = new Set([...(hoja ?? "").matchAll(/var\((--[a-z0-9-]+)/g)].map((m) => m[1]));
    expect(usados.size).toBeGreaterThan(5);
    const tokens = await import("../../styles/tokens.css?raw");
    const definidos = new Set([...tokens.default.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
    expect([...usados].filter((v) => !definidos.has(v))).toEqual([]);
  });
});
