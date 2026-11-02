/** Tipos del panel admin C-12: usuarios del consultorio (sin `any`). */
import type { Rol } from "../../shared/api-client";

export type { Rol };

export interface UsuarioAdmin {
  id: number;
  nombre: string;
  email: string;
  rol: Rol;
  activo: boolean;
}

export interface DatosAltaUsuario {
  nombre: string;
  email: string;
  password: string;
  rol: Rol;
}

export const ROLES: readonly Rol[] = ["admin", "odontologo", "secretaria"];

export const ETIQUETA_ROL: Record<Rol, string> = {
  admin: "Administrador",
  odontologo: "Odontólogo",
  secretaria: "Secretaría",
};

export const PASSWORD_MIN = 8;

export const esRol = (valor: unknown): valor is Rol =>
  valor === "admin" || valor === "odontologo" || valor === "secretaria";
