import { describe, expect, it } from "vitest";
import { claveDiaAR, horaAR } from "./fecha";

describe("fecha en America/Argentina/Buenos_Aires", () => {
  it("horaAR resta 3 h al instante UTC", () => {
    expect(horaAR("2026-10-12T20:00:00Z")).toBe("17:00");
    expect(horaAR("2026-10-12T20:30:00+00:00")).toBe("17:30");
  });

  it("horaAR cruza la medianoche hacia el dia anterior", () => {
    expect(horaAR("2026-10-12T02:15:00Z")).toBe("23:15");
  });

  it("horaAR respeta un offset explicito", () => {
    expect(horaAR("2026-10-12T17:00:00-03:00")).toBe("17:00");
  });

  it("claveDiaAR agrupa por dia local, no por dia UTC", () => {
    expect(claveDiaAR("2026-10-13T01:00:00Z")).toBe("2026-10-12");
    expect(claveDiaAR("2026-10-12T15:00:00Z")).toBe("2026-10-12");
  });
});
