import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OfertaEspera } from "./OfertaEspera";

const OFERTA = {
  nombre_pila: "Camila",
  inicio: "2026-10-30T13:30:00Z",
  fin: "2026-10-30T14:00:00Z",
  oferta_expira_en: "2099-01-01T00:00:00Z",
};

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** GET devuelve `get`; POST devuelve `post`. */
function stubFetch(get: Response, post?: Response): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((_u: unknown, init?: RequestInit) =>
    Promise.resolve((init?.method === "POST" ? post : get)?.clone() ?? respuestaJson({}, 500)),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function urlsPost(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return (fetchMock.mock.calls as [string, RequestInit | undefined][])
    .filter((c) => c[1]?.method === "POST")
    .map((c) => c[0]);
}

describe("OfertaEspera C-07 (pública por token)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("carga GET /lista-espera/oferta/:token y muestra nombre de pila y countdown", async () => {
    vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
    vi.setSystemTime(new Date("2026-10-28T12:00:00Z"));
    const fetchMock = stubFetch(
      respuestaJson({ ...OFERTA, oferta_expira_en: "2026-10-28T14:00:00Z" }, 200),
    );
    render(<OfertaEspera token="tok-1" />);
    expect(await screen.findByText(/camila/i)).toBeDefined();
    expect(String(fetchMock.mock.calls[0]?.[0])).toMatch(/\/lista-espera\/oferta\/tok-1$/);
    expect(screen.getByText("02:00:00")).toBeDefined();
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText("01:59:59")).toBeDefined();
  });

  it("aceptar llama POST /lista-espera/aceptar/:token y confirma el turno", async () => {
    const fetchMock = stubFetch(
      respuestaJson(OFERTA, 200),
      respuestaJson({ detail: "aceptado", turno_id: 9 }, 200),
    );
    render(<OfertaEspera token="tok-2" />);
    await userEvent.click(await screen.findByRole("button", { name: /aceptar turno/i }));
    expect(urlsPost(fetchMock)).toEqual([expect.stringMatching(/\/lista-espera\/aceptar\/tok-2$/)]);
    expect((await screen.findByRole("status")).textContent).toMatch(/turno confirmado/i);
    expect(screen.queryByRole("button", { name: /aceptar turno/i })).toBeNull();
  });

  it("rechazar llama POST /lista-espera/rechazar/:token y agradece la respuesta", async () => {
    const fetchMock = stubFetch(
      respuestaJson(OFERTA, 200),
      respuestaJson({ detail: "rechazado" }, 200),
    );
    render(<OfertaEspera token="tok-3" />);
    await userEvent.click(await screen.findByRole("button", { name: /no puedo/i }));
    expect(urlsPost(fetchMock)).toEqual([expect.stringMatching(/\/lista-espera\/rechazar\/tok-3$/)]);
    expect((await screen.findByRole("status")).textContent).toMatch(/gracias por avisar/i);
  });

  it("GET 404 muestra 'La oferta ya no existe' con el teléfono del consultorio", async () => {
    stubFetch(respuestaJson({ detail: "token inexistente" }, 404));
    render(<OfertaEspera token="tok-x" />);
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(/la oferta ya no existe/i);
    expect(alerta.textContent).toMatch(/\+54 11 4000-0000/);
  });

  it("GET 410 muestra que la oferta ya no está disponible con el teléfono", async () => {
    stubFetch(respuestaJson({ detail: "oferta no disponible" }, 410));
    render(<OfertaEspera token="tok-y" />);
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(/ya no est[aá] disponible/i);
    expect(alerta.textContent).toMatch(/\+54 11 4000-0000/);
  });

  it("aceptar con 410 'oferta expirada' dice que venció y da el teléfono", async () => {
    stubFetch(respuestaJson(OFERTA, 200), respuestaJson({ detail: "oferta expirada" }, 410));
    render(<OfertaEspera token="tok-4" />);
    await userEvent.click(await screen.findByRole("button", { name: /aceptar turno/i }));
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(/la oferta venci[oó]/i);
    expect(alerta.textContent).toMatch(/\+54 11 4000-0000/);
  });

  it("aceptar con 410 'oferta ya resuelta' dice que alguien más ya respondió", async () => {
    stubFetch(respuestaJson(OFERTA, 200), respuestaJson({ detail: "oferta ya resuelta" }, 410));
    render(<OfertaEspera token="tok-5" />);
    await userEvent.click(await screen.findByRole("button", { name: /aceptar turno/i }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/ya respondi[oó]/i);
  });

  it("aceptar con 409 informa que el horario se ocupó y lista alternativas", async () => {
    stubFetch(
      respuestaJson(OFERTA, 200),
      respuestaJson(
        {
          detail: "hueco ocupado",
          alternativas: [{ inicio: "2026-10-30T15:00:00Z", fin: "2026-10-30T15:30:00Z" }],
        },
        409,
      ),
    );
    render(<OfertaEspera token="tok-6" />);
    await userEvent.click(await screen.findByRole("button", { name: /aceptar turno/i }));
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(/horario ya fue ocupado/i);
    expect(alerta.textContent).toMatch(/\+54 11 4000-0000/);
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });

  it("aceptar con 404 muestra 'La oferta ya no existe'", async () => {
    stubFetch(respuestaJson(OFERTA, 200), respuestaJson({ detail: "token inexistente" }, 404));
    render(<OfertaEspera token="tok-7" />);
    await userEvent.click(await screen.findByRole("button", { name: /aceptar turno/i }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/la oferta ya no existe/i);
  });

  it("con el countdown en cero deshabilita Aceptar", async () => {
    vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
    vi.setSystemTime(new Date("2026-10-28T12:00:00Z"));
    stubFetch(respuestaJson({ ...OFERTA, oferta_expira_en: "2026-10-28T12:00:02Z" }, 200));
    render(<OfertaEspera token="tok-8" />);
    const boton = await screen.findByRole("button", { name: /aceptar turno/i });
    expect((boton as HTMLButtonElement).disabled).toBe(false);
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect((screen.getByRole("button", { name: /aceptar turno/i }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Oferta vencida")).toBeDefined();
  });
});
