import { useEffect, useState } from "react";
import { apiUrl } from "../shared/api-client";

const CONTACTO_FALLBACK: string =
  (import.meta.env["VITE_CONSULTORIO_TEL"] as string | undefined) ?? "+54 11 4000-0000";

type Estado = "cargando" | "confirmado" | "expirado" | "invalido";

function contactoDe(cuerpo: unknown): string {
  if (typeof cuerpo === "object" && cuerpo !== null) {
    const contacto = (cuerpo as Record<string, unknown>)["contacto"];
    if (typeof contacto === "string" && contacto !== "") return contacto;
  }
  return CONTACTO_FALLBACK;
}

interface Resultado {
  estado: Exclude<Estado, "cargando">;
  contacto: string | null;
}

/**
 * Una peticion por token: GET /confirmar/<token> consume el token en el primer 200, y bajo
 * React StrictMode el efecto corre dos veces; la segunda peticion daria 410 ("El link vencio").
 */
const PETICIONES = new Map<string, Promise<Resultado>>();

function confirmarUnaVez(token: string): Promise<Resultado> {
  const previa = PETICIONES.get(token);
  if (previa !== undefined) return previa;
  const nueva: Promise<Resultado> = fetch(apiUrl(`/confirmar/${token}`))
    .then(async (respuesta): Promise<Resultado> => {
      if (respuesta.status === 200) return { estado: "confirmado", contacto: null };
      const estado = respuesta.status === 410 ? "expirado" : "invalido";
      try {
        return { estado, contacto: contactoDe((await respuesta.json()) as unknown) };
      } catch {
        return { estado: "invalido", contacto: null };
      }
    })
    .catch((): Resultado => ({ estado: "invalido", contacto: null }));
  PETICIONES.set(token, nueva);
  return nueva;
}

/** Confirmacion por token C-05: cargando|confirmado|expirado|invalido (sin Bearer). */
export function Confirmar(props: { token: string }): JSX.Element {
  const [estado, setEstado] = useState<Estado>("cargando");
  const [contacto, setContacto] = useState<string>(CONTACTO_FALLBACK);

  useEffect(() => {
    if (props.token === "") {
      setEstado("invalido");
      return;
    }
    let vivo = true;
    void confirmarUnaVez(props.token).then((resultado) => {
      if (!vivo) return;
      if (resultado.contacto !== null) setContacto(resultado.contacto);
      setEstado(resultado.estado);
    });
    return (): void => {
      vivo = false;
    };
  }, [props.token]);


  return (
    <section>
      <h1>Confirmá tu asistencia</h1>
      {estado === "cargando" && <p>Confirmando…</p>}
      {estado === "confirmado" && <p>¡Turno confirmado! Te esperamos.</p>}
      {estado === "expirado" && (
        <div>
          <p>El link venció. Llamá al consultorio para reprogramar:</p>
          <p>{contacto}</p>
        </div>
      )}
      {estado === "invalido" && (
        <div>
          <p>Link inválido. Si tenés dudas, llamá al consultorio:</p>
          <p>{contacto}</p>
        </div>
      )}
    </section>
  );
}
