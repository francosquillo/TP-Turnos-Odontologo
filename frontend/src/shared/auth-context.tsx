import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

/** Stub C-01: la autenticación real (JWT + RBAC) llega en C-03. */

export type Rol = "admin" | "odontologo" | "secretaria";

export interface Sesion {
  email: string;
  rol: Rol;
}

interface AuthContexto {
  sesion: Sesion | null;
  iniciarSesion: (sesion: Sesion) => void;
  cerrarSesion: () => void;
}

const Contexto = createContext<AuthContexto | null>(null);

export function AuthProveedor({ children }: { children: ReactNode }): JSX.Element {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const valor = useMemo<AuthContexto>(
    () => ({
      sesion,
      iniciarSesion: (s: Sesion): void => setSesion(s),
      cerrarSesion: (): void => setSesion(null),
    }),
    [sesion],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAuth(): AuthContexto {
  const ctx = useContext(Contexto);
  if (ctx === null) throw new Error("useAuth requiere <AuthProveedor>");
  return ctx;
}
