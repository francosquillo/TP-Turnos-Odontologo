import { describe, expect, it } from "vitest";

// Lee el codigo fuente de produccion del feature (sin tests ni fixtures).
const fuentes = import.meta.glob<string>(
  ["./*.ts", "./*.tsx", "!./*.test.ts", "!./*.test.tsx", "!./testing.ts"],
  { query: "?raw", import: "default", eager: true },
);

describe("odontograma sin consola (D-12)", () => {
  it("encuentra los archivos de produccion del feature", () => {
    const nombres = Object.keys(fuentes).map((n) => n.replace("./", ""));
    expect(nombres).toEqual(
      expect.arrayContaining(["api.ts", "tipos.ts", "Grilla.tsx", "PiezaDetalle.tsx", "OdontogramaPage.tsx"]),
    );
  });

  it("test_odontograma_sin_console: ningun archivo del feature usa console", () => {
    const culpables = Object.entries(fuentes)
      .filter(([, codigo]) => /\bconsole\s*\./.test(codigo))
      .map(([nombre]) => nombre);
    expect(culpables).toEqual([]);
  });
});
