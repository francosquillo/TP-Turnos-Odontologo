import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PanelCobertura } from "./PanelCobertura";
import type { PlanDelCatalogo, PlanPaciente, ValidadorCobertura } from "./cobertura-tipos";

const respuestaJson = (cuerpo: unknown, status = 200): Response =>
  new Response(JSON.stringify(cuerpo), { status, headers: { "Content-Type": "application/json" } });

const PLANES: PlanDelCatalogo[] = [
  { id: 1, obra_social_id: 1, obra_social_nombre: "OS Ficticia Demo", nombre: "Plan Base", activo: true, created_at: "2026-10-01T12:00:00Z" },
  { id: 2, obra_social_id: 1, obra_social_nombre: "OS Ficticia Demo", nombre: "Plan Plus", activo: true, created_at: "2026-10-01T12:00:00Z" },
  { id: 3, obra_social_id: 1, obra_social_nombre: "OS Ficticia Demo", nombre: "Plan Viejo", activo: false, created_at: "2026-10-01T12:00:00Z" },
];

const TRATAMIENTOS = [
  { id: 10, codigo: "OBT-001", codigo_nomenclador: "N-003", nombre: "Obturación simple", precio_base: "15000.00" },
  { id: 11, codigo: "PRO-001", codigo_nomenclador: "N-002", nombre: "Limpieza y profilaxis", precio_base: "12000.00" },
];

const SIN_PLAN: PlanPaciente = { paciente_id: 3, plan_id: null, plan_nombre: null, obra_social_id: null, obra_social_nombre: null };
const CON_PLAN: PlanPaciente = { paciente_id: 3, plan_id: 1, plan_nombre: "Plan Base", obra_social_id: 1, obra_social_nombre: "OS Ficticia Demo" };

function validador(parcial: Partial<ValidadorCobertura>): ValidadorCobertura {
  return {
    estado: "cubierto", paciente_id: 3, tratamiento_id: 10, plan_id: 1, precio: "15000.00",
    arancel: "10500.00", cubierto: "10500.00", a_cargo: "4500.00", porcentaje: "70.00", fecha: "2026-10-31",
    ...parcial,
  };
}

interface Mundo {
  plan: PlanPaciente;
  validadores?: Record<number, ValidadorCobertura>;
  forzadas?: Record<string, Response>;
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    const forzada = mundo.forzadas?.[`${metodo} ${ruta}`];
    if (forzada !== undefined) return Promise.resolve(forzada.clone());
    if (ruta === "/pacientes/3/plan" && metodo === "GET") return Promise.resolve(respuestaJson(mundo.plan));
    if (ruta === "/pacientes/3/plan" && metodo === "PUT") {
      const { plan_id } = JSON.parse(String(init?.body)) as { plan_id: number | null };
      const elegido = PLANES.find((p) => p.id === plan_id);
      mundo.plan = {
        paciente_id: 3, plan_id: plan_id, plan_nombre: elegido?.nombre ?? null,
        obra_social_id: elegido?.obra_social_id ?? null, obra_social_nombre: elegido?.obra_social_nombre ?? null,
      };
      return Promise.resolve(respuestaJson(mundo.plan));
    }
    if (ruta === "/planes") return Promise.resolve(respuestaJson(PLANES));
    if (ruta === "/tratamientos") return Promise.resolve(respuestaJson(TRATAMIENTOS));
    const val = /^\/validador-cobertura\?paciente_id=3&tratamiento_id=(\d+)$/.exec(ruta);
    if (val !== null) {
      const v = mundo.validadores?.[Number(val[1])];
      return Promise.resolve(v === undefined ? respuestaJson({ detail: "tratamiento inexistente" }, 404) : respuestaJson(v));
    }
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PanelCobertura: plan del paciente", () => {
  it("muestra el plan y su obra social, y ofrece solo planes activos", async () => {
    stubFetch({ plan: CON_PLAN });
    render(<PanelCobertura pacienteId={3} />);
    expect((await screen.findByText(/Plan actual/)).textContent).toContain("Plan Base");
    expect(screen.getByText(/Plan actual/).textContent).toContain("OS Ficticia Demo");
    const opciones = within(screen.getByLabelText("Plan del paciente")).getAllByRole("option").map((o) => o.textContent);
    expect(opciones).toEqual(["Sin plan", "OS Ficticia Demo · Plan Base", "OS Ficticia Demo · Plan Plus"]);
  });

  it("un paciente sin plan lo dice con texto", async () => {
    stubFetch({ plan: SIN_PLAN });
    render(<PanelCobertura pacienteId={3} />);
    expect((await screen.findByText(/Plan actual/)).textContent).toContain("Sin plan de obra social");
  });

  it("asignar un plan lo envia por PUT y el panel lo muestra", async () => {
    const fetchMock = stubFetch({ plan: SIN_PLAN });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Plan del paciente"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Guardar plan" }));
    expect((await screen.findByText(/Plan actual: Plan Plus/)).textContent).toContain("OS Ficticia Demo");
    const put = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "PUT") as [string, RequestInit];
    expect(JSON.parse(String(put[1].body))).toEqual({ plan_id: 2 });
  });

  it("quitar el plan envia plan_id null", async () => {
    const fetchMock = stubFetch({ plan: CON_PLAN });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Plan del paciente"), "");
    await userEvent.click(screen.getByRole("button", { name: "Guardar plan" }));
    expect((await screen.findByText(/Plan actual/)).textContent).toContain("Sin plan de obra social");
    const put = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "PUT") as [string, RequestInit];
    expect(JSON.parse(String(put[1].body))).toEqual({ plan_id: null });
  });

  it("si el servidor rechaza el plan (409) muestra el mensaje y conserva lo elegido", async () => {
    stubFetch({ plan: SIN_PLAN, forzadas: { "PUT /pacientes/3/plan": respuestaJson({ detail: "el plan no existe o está inactivo" }, 409) } });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Plan del paciente"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Guardar plan" }));
    expect(await screen.findByText(/el plan no existe o está inactivo/)).toBeDefined();
    expect((screen.getByLabelText("Plan del paciente") as HTMLSelectElement).value).toBe("1");
  });
});

describe("PanelCobertura: validador", () => {
  it("cubierto: muestra cubierto, a cargo y porcentaje tal como los da el servidor", async () => {
    stubFetch({ plan: CON_PLAN, validadores: { 10: validador({}) } });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Tratamiento"), "10");
    const resultado = await screen.findByLabelText("Resultado de la cobertura");
    expect(resultado.textContent).toContain("Cubierto por la obra social");
    expect(resultado.textContent).toContain("$ 10.500,00");
    expect(resultado.textContent).toContain("$ 4.500,00");
    expect(resultado.textContent).toContain("70.00 %");
  });

  it("sin arancel: todo el precio queda a cargo del paciente", async () => {
    stubFetch({
      plan: CON_PLAN,
      validadores: { 11: validador({ estado: "sin_arancel", tratamiento_id: 11, precio: "12000.00", arancel: null, cubierto: "0.00", a_cargo: "12000.00", porcentaje: "0.00" }) },
    });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Tratamiento"), "11");
    const resultado = await screen.findByLabelText("Resultado de la cobertura");
    expect(resultado.textContent).toContain("Sin arancel vigente");
    expect(resultado.textContent).toContain("$ 12.000,00");
  });

  it("sin plan: lo dice y todo queda a cargo del paciente", async () => {
    stubFetch({
      plan: SIN_PLAN,
      validadores: { 10: validador({ estado: "sin_plan", plan_id: null, arancel: null, cubierto: "0.00", a_cargo: "15000.00", porcentaje: "0.00" }) },
    });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Tratamiento"), "10");
    const resultado = await screen.findByLabelText("Resultado de la cobertura");
    expect(resultado.textContent).toContain("El paciente no tiene un plan activo");
    expect(resultado.textContent).toContain("$ 15.000,00");
  });

  it("consulta el validador del servidor con paciente y tratamiento (no calcula nada en el cliente)", async () => {
    const fetchMock = stubFetch({ plan: CON_PLAN, validadores: { 10: validador({ cubierto: "1.00", a_cargo: "2.00", porcentaje: "33.33" }) } });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Tratamiento"), "10");
    const resultado = await screen.findByLabelText("Resultado de la cobertura");
    // Los importes del resultado son los del servidor aunque no sean coherentes con el precio base.
    expect(resultado.textContent).toContain("$ 1,00");
    expect(resultado.textContent).toContain("$ 2,00");
    expect(resultado.textContent).toContain("33.33 %");
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/validador-cobertura?paciente_id=3&tratamiento_id=10"))).toBe(true);
  });

  it("un error del validador se muestra sin romper el panel", async () => {
    stubFetch({ plan: CON_PLAN, validadores: {} });
    render(<PanelCobertura pacienteId={3} />);
    await screen.findByText(/Plan actual/);
    await userEvent.selectOptions(screen.getByLabelText("Tratamiento"), "10");
    expect(await screen.findByText(/tratamiento inexistente/)).toBeDefined();
    expect(screen.getByLabelText("Plan del paciente")).toBeDefined();
  });
});

describe("PanelCobertura: fallas de carga", () => {
  it("si no se pueden cargar los datos lo informa sin usar los roles alert ni status (la cuenta sigue usable)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respuestaJson({ detail: "ruta no prevista" }, 404)));
    render(<PanelCobertura pacienteId={3} />);
    expect(await screen.findByText(/No se pudo cargar la cobertura/)).toBeDefined();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("PanelCobertura sin aritmetica de dinero", () => {
  const fuentes = import.meta.glob<string>(
    ["./PanelCobertura.tsx", "./cobertura-api.ts", "./cobertura-tipos.ts"],
    { query: "?raw", import: "default", eager: true },
  );

  it("el codigo no convierte importes a numero ni usa console", () => {
    expect(Object.keys(fuentes)).toHaveLength(3);
    for (const [nombre, codigo] of Object.entries(fuentes)) {
      expect(codigo, nombre).not.toMatch(/parseFloat|Number\(\s*(monto|importe|precio|cubierto|a_cargo|porcentaje)/);
      expect(codigo, nombre).not.toMatch(/\bconsole\s*\./);
      expect(codigo, nombre).not.toMatch(/:\s*any\b|<any>|\bas any\b/);
    }
  });
});
