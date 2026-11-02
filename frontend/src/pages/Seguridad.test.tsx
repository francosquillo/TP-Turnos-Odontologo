import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Seguridad } from "./Seguridad";

const HECHOS = {
  datos_ficticios: true,
  declaracion: "Todos los datos de esta demostración son ficticios y de prueba.",
  hash_contrasenas: "argon2",
  access_token_min: 15,
  refresh_rotativo: true,
  whatsapp_modo: "mock",
  whatsapp_sin_datos_clinicos: true,
  google_calendar_habilitado: false,
  google_calendar_nota: "Google Calendar no sincroniza turnos en esta versión.",
  auditoria: ["Sobreturnos: quién lo autorizó y el motivo."],
  respaldos: ["Los datos viven en un volumen Docker local."],
  cifrado: "Cifrado en tránsito y en reposo: pendiente para producción (RN-GL-03).",
};

function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Seguridad C-12 (pública)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("muestra los hechos que devuelve GET /seguridad, sin enviar Bearer", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respuestaJson(HECHOS));
    vi.stubGlobal("fetch", fetchMock);
    render(<Seguridad />);
    expect(await screen.findByText(/datos de esta demostración son ficticios/i)).toBeDefined();
    expect(screen.getByText(/15 minutos/i)).toBeDefined();
    expect(screen.getByText(/argon2/i)).toBeDefined();
    expect(screen.getByText(/sobreturnos/i)).toBeDefined();
    expect(screen.getByText(/volumen docker local/i)).toBeDefined();
    expect(screen.getByText(/RN-GL-03/)).toBeDefined();
    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/seguridad$/);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    expect(new Headers(init?.headers).has("Authorization")).toBe(false);
  });

  it("refleja la configuración recibida: WhatsApp real y token de 45 minutos", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(respuestaJson({ ...HECHOS, access_token_min: 45, whatsapp_modo: "real" })),
    );
    render(<Seguridad />);
    expect(await screen.findByText(/45 minutos/i)).toBeDefined();
    expect(screen.queryByText(/15 minutos/i)).toBeNull();
    expect(screen.getByText(/WhatsApp real/i)).toBeDefined();
  });

  it("con error del backend muestra un mensaje y ninguna afirmación", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaJson({ detail: "boom" }, 500)));
    render(<Seguridad />);
    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.queryByText(/ficticios/i)).toBeNull();
    expect(screen.queryByText(/argon2/i)).toBeNull();
    expect(screen.queryByText(/protegida/i)).toBeNull();
  });

  it("sin conexión o con respuesta de forma inesperada muestra el error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("red caída")));
    const { unmount } = render(<Seguridad />);
    expect(await screen.findByRole("alert")).toBeDefined();
    unmount();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaJson({ datos_ficticios: true })));
    render(<Seguridad />);
    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.queryByText(/argon2/i)).toBeNull();
  });
});
