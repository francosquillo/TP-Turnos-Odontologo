import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UsuariosPage } from "./UsuariosPage";
import type { UsuarioAdmin } from "./tipos";

function respuestaJson(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const usuario = (parcial: Partial<UsuarioAdmin> = {}): UsuarioAdmin => ({
  id: 1,
  nombre: "Admin Demo",
  email: "admin@example.com",
  rol: "admin",
  activo: true,
  ...parcial,
});

interface Mundo {
  usuarios: UsuarioAdmin[];
  forzadas?: Record<string, Response>;
}

function stubFetch(mundo: Mundo): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockImplementation((url: unknown, init?: RequestInit) => {
    const ruta = String(url).replace(/^https?:\/\/[^/]+/, "");
    const metodo = init?.method ?? "GET";
    const forzada = mundo.forzadas?.[`${metodo} ${ruta}`];
    if (forzada !== undefined) return Promise.resolve(forzada.clone());
    const cuerpo = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : {};
    if (ruta === "/admin/usuarios" && metodo === "GET") return Promise.resolve(respuestaJson(mundo.usuarios));
    if (ruta === "/admin/usuarios" && metodo === "POST") {
      const nuevo = usuario({
        id: 50,
        nombre: String(cuerpo["nombre"]),
        email: String(cuerpo["email"]),
        rol: cuerpo["rol"] as UsuarioAdmin["rol"],
      });
      mundo.usuarios = [...mundo.usuarios, nuevo];
      return Promise.resolve(respuestaJson(nuevo, 201));
    }
    const una = /^\/admin\/usuarios\/(\d+)(\/desactivar)?$/.exec(ruta);
    if (una !== null && metodo === "PATCH") {
      const id = Number(una[1]);
      const actual = mundo.usuarios.find((u) => u.id === id);
      if (actual === undefined) return Promise.resolve(respuestaJson({ detail: "no existe" }, 404));
      const cambio: Partial<UsuarioAdmin> = una[2] !== undefined ? { activo: false } : {};
      if (typeof cuerpo["rol"] === "string") cambio.rol = cuerpo["rol"] as UsuarioAdmin["rol"];
      if (cuerpo["activo"] === true) cambio.activo = true;
      const nuevo = { ...actual, ...cambio };
      mundo.usuarios = mundo.usuarios.map((u) => (u.id === id ? nuevo : u));
      return Promise.resolve(respuestaJson(nuevo));
    }
    return Promise.resolve(respuestaJson({ detail: "ruta no prevista" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const llamadas = (fetchMock: ReturnType<typeof vi.fn>, metodo: string): [string, RequestInit][] =>
  (fetchMock.mock.calls as [string, RequestInit | undefined][])
    .filter((c) => (c[1]?.method ?? "GET") === metodo)
    .map((c) => [c[0].replace(/^https?:\/\/[^/]+/, ""), c[1] ?? {}]);

const dosUsuarios = (): Mundo => ({
  usuarios: [
    usuario(),
    usuario({ id: 2, nombre: "Sofía Secretaria", email: "sofia@example.com", rol: "secretaria" }),
  ],
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UsuariosPage C-12", () => {
  it("lista nombre, correo, rol y estado de cada usuario", async () => {
    stubFetch({
      usuarios: [
        ...dosUsuarios().usuarios,
        usuario({ id: 3, nombre: "Omar Odonto", email: "omar@example.com", rol: "odontologo", activo: false }),
      ],
    });
    render(<UsuariosPage />);
    const fila = (await screen.findByText("Sofía Secretaria")).closest("tr");
    expect(fila).not.toBeNull();
    const celdas = within(fila as HTMLElement);
    expect(celdas.getByText("sofia@example.com")).toBeDefined();
    expect((celdas.getByLabelText("Rol de Sofía Secretaria") as HTMLSelectElement).value).toBe("secretaria");
    expect(celdas.getByText("Activo")).toBeDefined();
    const inactivo = screen.getByText("Omar Odonto").closest("tr") as HTMLElement;
    expect(within(inactivo).getByText("Inactivo")).toBeDefined();
  });

  it("da de alta un usuario con el formulario y lo muestra en la lista", async () => {
    const fetchMock = stubFetch(dosUsuarios());
    render(<UsuariosPage />);
    await screen.findByText("Sofía Secretaria");
    await userEvent.type(screen.getByLabelText("Nombre"), "Nora Nueva");
    await userEvent.type(screen.getByLabelText("Correo electrónico"), "nora@example.com");
    await userEvent.type(screen.getByLabelText("Contraseña inicial"), "Clave-1234");
    await userEvent.selectOptions(screen.getByLabelText("Rol"), "odontologo");
    await userEvent.click(screen.getByRole("button", { name: "Crear usuario" }));
    expect(await screen.findByText("nora@example.com")).toBeDefined();
    const [ruta, init] = llamadas(fetchMock, "POST")[0] ?? ["", {}];
    expect(ruta).toBe("/admin/usuarios");
    expect(JSON.parse(String(init.body))).toEqual({
      nombre: "Nora Nueva",
      email: "nora@example.com",
      password: "Clave-1234",
      rol: "odontologo",
    });
    expect((screen.getByLabelText("Contraseña inicial") as HTMLInputElement).value).toBe("");
  });

  it("no envía el alta con la contraseña corta y avisa el mínimo", async () => {
    const fetchMock = stubFetch(dosUsuarios());
    render(<UsuariosPage />);
    await screen.findByText("Sofía Secretaria");
    await userEvent.type(screen.getByLabelText("Nombre"), "Nora Nueva");
    await userEvent.type(screen.getByLabelText("Correo electrónico"), "nora@example.com");
    await userEvent.type(screen.getByLabelText("Contraseña inicial"), "corta");
    await userEvent.click(screen.getByRole("button", { name: "Crear usuario" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/8 caracteres/);
    expect(llamadas(fetchMock, "POST")).toHaveLength(0);
  });

  it("muestra el motivo del backend si el correo ya existe (409)", async () => {
    const mundo = dosUsuarios();
    mundo.forzadas = { "POST /admin/usuarios": respuestaJson({ detail: "ya existe un usuario con ese email" }, 409) };
    stubFetch(mundo);
    render(<UsuariosPage />);
    await screen.findByText("Sofía Secretaria");
    await userEvent.type(screen.getByLabelText("Nombre"), "Otra Sofía");
    await userEvent.type(screen.getByLabelText("Correo electrónico"), "SOFIA@example.com");
    await userEvent.type(screen.getByLabelText("Contraseña inicial"), "Clave-1234");
    await userEvent.click(screen.getByRole("button", { name: "Crear usuario" }));
    expect((await screen.findByRole("alert")).textContent).toContain("ya existe un usuario con ese email");
  });

  it("cambia el rol de un usuario con PATCH y refleja el rol nuevo", async () => {
    const fetchMock = stubFetch(dosUsuarios());
    render(<UsuariosPage />);
    const selector = await screen.findByLabelText("Rol de Sofía Secretaria");
    await userEvent.selectOptions(selector, "odontologo");
    await waitFor(() => {
      expect((screen.getByLabelText("Rol de Sofía Secretaria") as HTMLSelectElement).value).toBe("odontologo");
    });
    const [ruta, init] = llamadas(fetchMock, "PATCH")[0] ?? ["", {}];
    expect(ruta).toBe("/admin/usuarios/2");
    expect(JSON.parse(String(init.body))).toEqual({ rol: "odontologo" });
  });

  it("desactiva y reactiva: cada uno usa su endpoint y el botón cambia", async () => {
    const fetchMock = stubFetch(dosUsuarios());
    render(<UsuariosPage />);
    const fila = (await screen.findByText("Sofía Secretaria")).closest("tr") as HTMLElement;
    await userEvent.click(within(fila).getByRole("button", { name: "Desactivar" }));
    expect(await within(fila).findByRole("button", { name: "Reactivar" })).toBeDefined();
    expect(within(fila).getByText("Inactivo")).toBeDefined();
    await userEvent.click(within(fila).getByRole("button", { name: "Reactivar" }));
    expect(await within(fila).findByRole("button", { name: "Desactivar" })).toBeDefined();
    const patch = llamadas(fetchMock, "PATCH");
    expect(patch[0]?.[0]).toBe("/admin/usuarios/2/desactivar");
    expect(patch[1]?.[0]).toBe("/admin/usuarios/2");
    expect(JSON.parse(String(patch[1]?.[1].body))).toEqual({ activo: true });
  });

  it("ante el 409 del último admin muestra el motivo del backend y la fila sigue activa", async () => {
    const motivo = "no se puede desactivar/eliminar al ultimo admin activo (RN-AU-03)";
    const mundo = dosUsuarios();
    mundo.forzadas = { "PATCH /admin/usuarios/1/desactivar": respuestaJson({ detail: motivo }, 409) };
    stubFetch(mundo);
    render(<UsuariosPage />);
    const fila = (await screen.findByText("Admin Demo")).closest("tr") as HTMLElement;
    await userEvent.click(within(fila).getByRole("button", { name: "Desactivar" }));
    expect((await screen.findByRole("alert")).textContent).toContain(motivo);
    expect(within(fila).getByText("Activo")).toBeDefined();
    expect(within(fila).getByRole("button", { name: "Desactivar" })).toBeDefined();
  });

  it("ante el 409 al cambiar el rol del último admin muestra el motivo y el selector vuelve al rol real", async () => {
    const motivo = "no se puede quitar el rol admin al ultimo admin activo (RN-AU-03)";
    const mundo = dosUsuarios();
    mundo.forzadas = { "PATCH /admin/usuarios/1": respuestaJson({ detail: motivo }, 409) };
    stubFetch(mundo);
    render(<UsuariosPage />);
    const selector = await screen.findByLabelText("Rol de Admin Demo");
    await userEvent.selectOptions(selector, "secretaria");
    expect((await screen.findByRole("alert")).textContent).toContain(motivo);
    expect((screen.getByLabelText("Rol de Admin Demo") as HTMLSelectElement).value).toBe("admin");
  });

  it("no ofrece eliminar usuarios", async () => {
    stubFetch(dosUsuarios());
    render(<UsuariosPage />);
    await screen.findByText("Sofía Secretaria");
    expect(screen.queryByRole("button", { name: /eliminar|borrar/i })).toBeNull();
  });

  it("si no puede cargar la lista muestra un error", async () => {
    stubFetch({ usuarios: [], forzadas: { "GET /admin/usuarios": respuestaJson({ detail: "sin permiso" }, 403) } });
    render(<UsuariosPage />);
    expect((await screen.findByRole("alert")).textContent).toContain("sin permiso");
  });
});
