import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ExportacionTotal } from "./ExportacionTotal";

function respuestaZip(disposicion: string | null): Response {
  const headers = new Headers({ "Content-Type": "application/zip" });
  if (disposicion !== null) headers.set("Content-Disposition", disposicion);
  return new Response("PK", { status: 200, headers });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ExportacionTotal C-12", () => {
  it("pide /admin/export-total con la sesión y entrega el ZIP con el nombre del servidor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaZip('attachment; filename="export-total-2026-11-02.zip"'));
    vi.stubGlobal("fetch", fetchMock);
    const guardar = vi.fn();
    render(<ExportacionTotal guardar={guardar} />);
    await userEvent.click(screen.getByRole("button", { name: "Descargar exportación total" }));
    await vi.waitFor(() => expect(guardar).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/admin\/export-total$/);
    const [blob, nombre] = guardar.mock.calls[0] as [Blob, string];
    expect(nombre).toBe("export-total-2026-11-02.zip");
    expect(blob.size).toBe(2);
  });

  it("si el servidor no manda el nombre usa export-total.zip", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaZip(null)));
    const guardar = vi.fn();
    render(<ExportacionTotal guardar={guardar} />);
    await userEvent.click(screen.getByRole("button", { name: "Descargar exportación total" }));
    await vi.waitFor(() => expect(guardar).toHaveBeenCalledTimes(1));
    expect(guardar.mock.calls[0]?.[1]).toBe("export-total.zip");
  });

  it("ante un error muestra el motivo y no descarga nada", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "sin permiso" }), {
          status: 403,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const guardar = vi.fn();
    render(<ExportacionTotal guardar={guardar} />);
    await userEvent.click(screen.getByRole("button", { name: "Descargar exportación total" }));
    expect((await screen.findByRole("alert")).textContent).toContain("sin permiso");
    expect(guardar).not.toHaveBeenCalled();
  });

  it("avisa que incluye datos clínicos y que es para el administrador", () => {
    render(<ExportacionTotal guardar={vi.fn()} />);
    expect(screen.getByText(/datos clínicos/i)).toBeDefined();
  });
});
