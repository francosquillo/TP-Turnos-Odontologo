import { describe, expect, it } from "vitest";
import { estadoDeSaldo, formatearMoneda } from "./moneda";

describe("formatearMoneda", () => {
  it("formatea texto decimal en es-AR", () => {
    expect(formatearMoneda("2501.00")).toBe("$ 2.501,00");
    expect(formatearMoneda("1234567.5")).toBe("$ 1.234.567,50");
    expect(formatearMoneda("15000")).toBe("$ 15.000,00");
  });

  it("negativo", () => {
    expect(formatearMoneda("-500.00")).toBe("-$ 500,00");
    expect(formatearMoneda("-2001.5")).toBe("-$ 2.001,50");
  });

  it("cero", () => {
    expect(formatearMoneda("0.00")).toBe("$ 0,00");
    expect(formatearMoneda("0")).toBe("$ 0,00");
  });

  it("no pierde precision en importes grandes (sin aritmetica de punto flotante)", () => {
    expect(formatearMoneda("49500000000000.50")).toBe("$ 49.500.000.000.000,50");
    expect(formatearMoneda("9007199254740993.01")).toBe("$ 9.007.199.254.740.993,01");
  });

  it("una forma inesperada no se inventa: muestra un guion", () => {
    expect(formatearMoneda("abc")).toBe("—");
    expect(formatearMoneda("")).toBe("—");
    expect(formatearMoneda("12,5")).toBe("—");
  });
});

describe("estadoDeSaldo", () => {
  it("clasifica el texto decimal sin aritmetica", () => {
    expect(estadoDeSaldo("500.00")).toBe("debe");
    expect(estadoDeSaldo("0.00")).toBe("sin-deuda");
    expect(estadoDeSaldo("-0.00")).toBe("sin-deuda");
    expect(estadoDeSaldo("-200.50")).toBe("a-favor");
    expect(estadoDeSaldo("0.01")).toBe("debe");
  });
});
