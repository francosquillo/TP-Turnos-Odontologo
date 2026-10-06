import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("App shell C-01", () => {
  it("renderiza la navegacion con las 3 paginas placeholder", () => {
    render(<App />);
    expect(screen.getByText("Reservar")).toBeDefined();
    expect(screen.getByText("Confirmar")).toBeDefined();
    expect(screen.getByText("Seguridad")).toBeDefined();
  });
});
