import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ListaEsperaPage } from "./ListaEsperaPage";

const AHORA = new Date("2026-10-28T12:00:00Z");

function entrada(sobreescribir: Record<string, unknown>): Record<string, unknown> {
  return {
    id: 1,
    paciente_id: 10,
    profesional_id: 1,
    especialidad: null,
    preferencia_horaria: null,
    estado: "activa",
    oferta_expira_en: null,
    oferta_hueco: null,
    motivo_baja: null,
    created_at: "2026-10-26T10:00:00Z",
    ...sobreescribir,
  };
}

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(cola: unknown[]): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((_url: unknown, init?: RequestInit) => {
    const metodo = init?.method ?? "GET";
    if (metodo === "GET") return Promise.resolve(respuestaJson(cola, 200));
    return Promise.resolve(respuestaJson(entrada({}), 200));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function llamadasPost(fetchMock: ReturnType<typeof vi.fn>): [string, RequestInit][] {
  return (fetchMock.mock.calls as [string, RequestInit | undefined][]).filter(
    (llamada): llamada is [string, RequestInit] => llamada[1]?.method === "POST",
  );
}

describe("ListaEsperaPage C-07 (staff)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("ordena la cola FIFO por created_at ascendente aunque llegue desordenada", async () => {
    stubFetch([
      entrada({ id: 3, created_at: "2026-10-27T10:00:00Z" }),
      entrada({ id: 1, created_at: "2026-10-25T10:00:00Z" }),
      entrada({ id: 2, created_at: "2026-10-26T10:00:00Z" }),
    ]);
    render(<ListaEsperaPage />);
    const items = await screen.findAllByRole("listitem");
    expect(items.map((li) => li.getAttribute("data-espera-id"))).toEqual(["1", "2", "3"]);
  });

  it("muestra el estado como texto (no solo color) en cada entrada", async () => {
    stubFetch([
      entrada({ id: 1, estado: "activa" }),
      entrada({ id: 2, estado: "convertida", created_at: "2026-10-26T11:00:00Z" }),
      entrada({ id: 3, estado: "vencida", created_at: "2026-10-26T12:00:00Z" }),
    ]);
    render(<ListaEsperaPage />);
    const items = await screen.findAllByRole("listitem");
    expect(within(items[0]!).getByText("Activa").getAttribute("data-espera")).toBe("activa");
    expect(within(items[1]!).getByText("Convertida").getAttribute("data-espera")).toBe("convertida");
    expect(within(items[2]!).getByText("Vencida").getAttribute("data-espera")).toBe("vencida");
  });

  describe("countdown", () => {
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] });
      vi.setSystemTime(AHORA);
    });

    it("deriva el countdown de oferta_expira_en y avanza cada segundo", async () => {
      stubFetch([
        entrada({
          estado: "ofrecida",
          oferta_expira_en: new Date(AHORA.getTime() + 5400_000).toISOString(),
        }),
      ]);
      render(<ListaEsperaPage />);
      expect(await screen.findByText("01:30:00")).toBeDefined();
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      expect(screen.getByText("01:29:59")).toBeDefined();
      expect(screen.queryByText("01:30:00")).toBeNull();
    });

    it("marca urgente el countdown con menos de 5 minutos", async () => {
      stubFetch([
        entrada({
          estado: "ofrecida",
          oferta_expira_en: new Date(AHORA.getTime() + 240_000).toISOString(),
        }),
      ]);
      render(<ListaEsperaPage />);
      const cuenta = await screen.findByText("00:04:00");
      expect(cuenta.getAttribute("data-urgente")).toBe("true");
    });

    it("al llegar a cero muestra 'Oferta vencida' en vez de un tiempo negativo", async () => {
      stubFetch([
        entrada({
          estado: "ofrecida",
          oferta_expira_en: new Date(AHORA.getTime() + 2000).toISOString(),
        }),
      ]);
      render(<ListaEsperaPage />);
      expect(await screen.findByText("00:00:02")).toBeDefined();
      act(() => {
        vi.advanceTimersByTime(3000);
      });
      const vencida = screen.getByText("Oferta vencida");
      expect(vencida.getAttribute("data-vencido")).toBe("true");
    });
  });

  it("convertir llama POST /lista-espera/:id/convertir solo en entradas ofrecidas", async () => {
    const fetchMock = stubFetch([
      entrada({ id: 7, estado: "ofrecida", oferta_expira_en: "2099-01-01T00:00:00Z" }),
      entrada({ id: 8, estado: "activa", created_at: "2026-10-26T11:00:00Z" }),
    ]);
    render(<ListaEsperaPage />);
    const botones = await screen.findAllByRole("button", { name: /convertir/i });
    expect(botones).toHaveLength(1);
    await userEvent.click(botones[0]!);
    const posts = llamadasPost(fetchMock);
    expect(posts.map(([url]) => url)).toEqual([expect.stringMatching(/\/lista-espera\/7\/convertir$/)]);
  });

  it("dar de baja exige motivo y envía motivo_baja", async () => {
    const fetchMock = stubFetch([entrada({ id: 5 })]);
    render(<ListaEsperaPage />);
    await userEvent.click(await screen.findByRole("button", { name: /dar de baja/i }));
    await userEvent.click(screen.getByRole("button", { name: /confirmar baja/i }));
    expect(screen.getByRole("alert").textContent).toMatch(/motivo/i);
    expect(llamadasPost(fetchMock)).toHaveLength(0);

    await userEvent.type(screen.getByLabelText(/motivo/i), "Paciente ya no necesita turno");
    await userEvent.click(screen.getByRole("button", { name: /confirmar baja/i }));
    const [url, init] = llamadasPost(fetchMock)[0]!;
    expect(url).toMatch(/\/lista-espera\/5\/baja$/);
    expect(JSON.parse(String(init.body))).toEqual({ motivo_baja: "Paciente ya no necesita turno" });
  });

  it("ofrecer hueco envía profesional, sillón y horario a POST /:id/ofrecer", async () => {
    const fetchMock = stubFetch([entrada({ id: 4, profesional_id: 2 })]);
    render(<ListaEsperaPage />);
    await userEvent.click(await screen.findByRole("button", { name: /ofrecer hueco/i }));
    await userEvent.type(screen.getByLabelText(/sill[oó]n/i), "3");
    await userEvent.type(screen.getByLabelText(/inicio/i), "2026-10-30T10:30");
    await userEvent.type(screen.getByLabelText(/fin/i), "2026-10-30T11:00");
    await userEvent.click(screen.getByRole("button", { name: /enviar oferta/i }));
    const [url, init] = llamadasPost(fetchMock)[0]!;
    expect(url).toMatch(/\/lista-espera\/4\/ofrecer$/);
    const cuerpo = JSON.parse(String(init.body)) as Record<string, unknown>;
    expect(cuerpo["profesional_id"]).toBe(2);
    expect(cuerpo["sillon_id"]).toBe(3);
    expect(String(cuerpo["inicio"])).toMatch(/^2026-10-30T/);
    expect(String(cuerpo["fin"])).toMatch(/^2026-10-30T/);
  });

  it("si la oferta manual da 409 muestra el error en un alert", async () => {
    const fetchMock = vi.fn().mockImplementation((_u: unknown, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "POST"
          ? respuestaJson({ detail: "ya tiene una oferta activa" }, 409)
          : respuestaJson([entrada({ id: 4, profesional_id: 2 })], 200),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<ListaEsperaPage />);
    await userEvent.click(await screen.findByRole("button", { name: /ofrecer hueco/i }));
    await userEvent.type(screen.getByLabelText(/sill[oó]n/i), "3");
    await userEvent.type(screen.getByLabelText(/inicio/i), "2026-10-30T10:30");
    await userEvent.type(screen.getByLabelText(/fin/i), "2026-10-30T11:00");
    await userEvent.click(screen.getByRole("button", { name: /enviar oferta/i }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/oferta activa/i);
  });
});
