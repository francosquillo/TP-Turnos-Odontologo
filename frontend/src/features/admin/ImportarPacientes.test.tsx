import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ImportarPacientes } from "./ImportarPacientes";

function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const REPORTE = {
  creados: 3,
  rechazados: 2,
  errores: [
    { fila: 5, motivo: "falta el apellido" },
    { fila: 6, motivo: "DNI repetido en el archivo (ya figura en la fila 2)" },
  ],
};

const archivoCsv = (): File => new File(["nombre,apellido\nAna,Ficticia\n"], "pacientes.csv", { type: "text/csv" });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ImportarPacientes C-12", () => {
  it("sin archivo el botón está deshabilitado", () => {
    render(<ImportarPacientes />);
    expect((screen.getByRole("button", { name: "Importar pacientes" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("sube el archivo y muestra creados, rechazados y la tabla de errores por fila", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(REPORTE));
    vi.stubGlobal("fetch", fetchMock);
    render(<ImportarPacientes />);
    await userEvent.upload(screen.getByLabelText("Archivo CSV o XLSX"), archivoCsv());
    await userEvent.click(screen.getByRole("button", { name: "Importar pacientes" }));
    expect(await screen.findByText(/3 pacientes creados/)).toBeDefined();
    expect(screen.getByText(/2 filas rechazadas/)).toBeDefined();
    const filas = within(screen.getByRole("table", { name: "Filas rechazadas" })).getAllByRole("row");
    expect(filas.map((f) => f.textContent)).toEqual([
      "FilaMotivo",
      "5falta el apellido",
      "6DNI repetido en el archivo (ya figura en la fila 2)",
    ]);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/pacientes\/import$/);
    expect(init.method).toBe("POST");
    const cuerpo = init.body as FormData;
    expect((cuerpo.get("archivo") as File).name).toBe("pacientes.csv");
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("con todas las filas válidas no muestra tabla de errores", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaJson({ creados: 1, rechazados: 0, errores: [] })));
    render(<ImportarPacientes />);
    await userEvent.upload(screen.getByLabelText("Archivo CSV o XLSX"), archivoCsv());
    await userEvent.click(screen.getByRole("button", { name: "Importar pacientes" }));
    expect(await screen.findByText(/1 paciente creado\b/)).toBeDefined();
    expect(screen.queryByRole("table", { name: "Filas rechazadas" })).toBeNull();
  });

  it("si el archivo no es válido (422) muestra el motivo y ningún resultado", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(respuestaJson({ detail: "faltan columnas obligatorias: apellido" }, 422)),
    );
    render(<ImportarPacientes />);
    await userEvent.upload(screen.getByLabelText("Archivo CSV o XLSX"), archivoCsv());
    await userEvent.click(screen.getByRole("button", { name: "Importar pacientes" }));
    expect((await screen.findByRole("alert")).textContent).toContain("faltan columnas obligatorias: apellido");
    expect(screen.queryByText(/creados/)).toBeNull();
  });
});
