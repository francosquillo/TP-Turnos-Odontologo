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
    fetch(apiUrl(`/confirmar/${props.token}`))
      .then((respuesta) => {
        if (!vivo) return;
        if (respuesta.status === 200) {
          setEstado("confirmado");
          return;
        }
        return respuesta
          .json()
          .then((cuerpo: unknown) => {
            if (!vivo) return;
            setContacto(contactoDe(cuerpo));
            setEstado(respuesta.status === 410 ? "expirado" : "invalido");
          })
          .catch(() => {
            if (vivo) setEstado("invalido");
          });
      })
      .catch(() => {
        if (vivo) setEstado("invalido");
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
