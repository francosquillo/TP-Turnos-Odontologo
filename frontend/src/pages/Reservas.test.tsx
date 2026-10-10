import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Reservas } from "./Reservas";

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const HUECOS = [
  { inicio: "2026-10-12T12:00:00+00:00", fin: "2026-10-12T12:30:00+00:00" },
  { inicio: "2026-10-12T12:30:00+00:00", fin: "2026-10-12T13:00:00+00:00" },
];

function mockFetch(impl: (url: unknown, init?: RequestInit) => Promise<Response>): void {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(impl));
}

async function buscarHuecos(usuario: ReturnType<typeof userEvent.setup>): Promise<void> {
  await usuario.type(screen.getByLabelText(/profesional/i), "1");
  await usuario.type(screen.getByLabelText(/d[ií]a/i), "2026-10-12");
  await usuario.click(screen.getByRole("button", { name: /buscar huecos/i }));
}

describe("Reservas C-05", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("elige hueco, completa formulario minimo y muestra exito", async () => {
    mockFetch((url, init) => {
      const u = String(url);
      if (u.includes("/disponibilidad")) return Promise.resolve(respuestaJson(HUECOS, 200));
      if (u.includes("/reservas") && init?.method === "POST") {
        return Promise.resolve(
          respuestaJson(
            { turno_id: 5, estado: "pendiente", token: "tok-demo", expira_en: "2026-10-04T12:00:00+00:00" },
            201,
          ),
        );
      }
      return Promise.resolve(respuestaJson({}, 404));
    });
    const usuario = userEvent.setup();
    render(<Reservas />);

    await buscarHuecos(usuario);
    const huecos = await screen.findAllByRole("button", { name: /09:00|12:00/i });
    expect(huecos.length).toBeGreaterThan(0);
    await usuario.click(huecos[0]);

    await usuario.type(screen.getByLabelText(/nombre/i), "Ana Ficticia");
    await usuario.type(screen.getByLabelText(/tel[eé]fono/i), "1150002222");
    await usuario.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    expect(await screen.findByText(/reserva creada/i)).toBeDefined();
    expect(screen.getByText(/whatsapp/i)).toBeDefined();
  });

  it("formulario incompleto bloquea el submit", async () => {
    mockFetch((url) => {
      if (String(url).includes("/disponibilidad")) return Promise.resolve(respuestaJson(HUECOS, 200));
      return Promise.resolve(respuestaJson({}, 404));
    });
    const usuario = userEvent.setup();
    render(<Reservas />);

    await buscarHuecos(usuario);
    const huecos = await screen.findAllByRole("button", { name: /09:00|12:00/i });
    await usuario.click(huecos[0]);

    // Sin nombre ni telefono: el boton sigue deshabilitado.
    expect(screen.getByRole("button", { name: /confirmar reserva/i })).toHaveProperty("disabled", true);
  });

  it("409 con alternativas re-oferta sin perder nombre y telefono", async () => {
    const llamadas: string[] = [];
    mockFetch((url, init) => {
      const u = String(url);
      if (u.includes("/disponibilidad")) return Promise.resolve(respuestaJson(HUECOS, 200));
      if (u.includes("/reservas") && init?.method === "POST") {
        llamadas.push(String(init?.body));
        if (llamadas.length === 1) {
          return Promise.resolve(
            respuestaJson(
              {
                detail: "hueco ocupado",
                alternativas: [
                  { inicio: "2026-10-12T12:30:00+00:00", fin: "2026-10-12T13:00:00+00:00" },
                ],
              },
              409,
            ),
          );
        }
        return Promise.resolve(
          respuestaJson({ turno_id: 6, estado: "pendiente", token: "tok-2", expira_en: "2026-10-04T12:00:00+00:00" }, 201),
        );
      }
      return Promise.resolve(respuestaJson({}, 404));
    });
    const usuario = userEvent.setup();
    render(<Reservas />);

    await buscarHuecos(usuario);
    const huecos = await screen.findAllByRole("button", { name: /09:00|12:00/i });
    await usuario.click(huecos[0]);
    await usuario.type(screen.getByLabelText(/nombre/i), "Ana Ficticia");
    await usuario.type(screen.getByLabelText(/tel[eé]fono/i), "1150002222");
    await usuario.click(screen.getByRole("button", { name: /confirmar reserva/i }));

    // Re-oferta visible y formulario conservado.
    const panel = await screen.findByText(/se acaba de ocupar/i);
    expect(panel).toBeDefined();
    expect((screen.getByLabelText(/nombre/i) as HTMLInputElement).value).toBe("Ana Ficticia");
    expect((screen.getByLabelText(/tel[eé]fono/i) as HTMLInputElement).value).toBe("1150002222");

    // Elegir la alternativa y reenviar conserva los datos.
    const region = panel.parentElement as HTMLElement;
    const alt = within(region.parentElement as HTMLElement).getAllByRole("button", { name: /09:30|12:30/i });
    await usuario.click(alt[0]);
    await usuario.click(screen.getByRole("button", { name: /confirmar reserva/i }));
    expect(await screen.findByText(/reserva creada/i)).toBeDefined();
    expect(llamadas.length).toBe(2);
    expect(llamadas[1]).toContain("Ana Ficticia");
  });
});
