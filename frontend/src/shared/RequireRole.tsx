import type { ReactNode } from "react";
import { useAuth } from "./auth-context";
import type { Rol } from "./api-client";

interface Props {
  roles: Rol[];
  children: ReactNode;
  alternativa?: ReactNode;
}

/** Guard declarativo (D-07): sin sesion muestra la alternativa o
 *  pide iniciar sesion; con rol no incluido muestra "sin permiso".
 *  El backend sigue siendo la autoridad (el 403 manda).
 */
export function RequireRole({ roles, children, alternativa }: Props): JSX.Element {
  const { sesion, cargando } = useAuth();

  if (cargando) return <p>Cargando sesión…</p>;
  if (sesion === null) {
    if (alternativa !== undefined) return <>{alternativa}</>;
    return <p>Iniciá sesión para continuar.</p>;
  }
  if (!roles.includes(sesion.rol)) return <p>sin permiso</p>;
  return <>{children}</>;
}
