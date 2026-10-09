import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  fetchConAuth,
  loginApi,
  logoutApi,
  meApi,
  refreshApi,
} from "./api-client";
import type { Rol } from "./api-client";

/** Sesion C-03 (D-07): access solo en memoria, refresh silencioso. */

export type { Rol };

export interface Sesion {
  email: string;
  rol: Rol;
}

interface AuthContexto {
  sesion: Sesion | null;
  cargando: boolean;
  iniciarSesion: (email: string, password: string) => Promise<void>;
  cerrarSesion: () => Promise<void>;
  fetchAutenticado: (input: string, init?: RequestInit) => Promise<Response>;
}

const Contexto = createContext<AuthContexto | null>(null);

export function AuthProveedor({ children }: { children: ReactNode }): JSX.Element {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [cargando, setCargando] = useState<boolean>(true);

  useEffect(() => {
    let vigente = true;
    refreshApi()
      .then((access) => {
        if (access === null || !vigente) return null;
        return meApi(access);
      })
      .then((yo) => {
        if (vigente && yo !== null) setSesion({ email: yo.email, rol: yo.rol });
      })
      .catch(() => {
        if (vigente) setSesion(null);
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return (): void => {
      vigente = false;
    };
  }, []);

  const valor = useMemo<AuthContexto>(
    () => ({
      sesion,
      cargando,
      iniciarSesion: async (email: string, password: string): Promise<void> => {
        const yo = await loginApi(email, password);
        setSesion({ email: yo.email, rol: yo.rol });
      },
      cerrarSesion: async (): Promise<void> => {
        await logoutApi();
        setSesion(null);
      },
      fetchAutenticado: (input: string, init?: RequestInit): Promise<Response> =>
        fetchConAuth(input, init, {
          alSesionExpirada: () => setSesion(null),
        }),
    }),
    [sesion, cargando],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useAuth(): AuthContexto {
  const ctx = useContext(Contexto);
  if (ctx === null) throw new Error("useAuth requiere <AuthProveedor>");
  return ctx;
}
