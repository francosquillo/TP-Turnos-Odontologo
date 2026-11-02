import { useEffect, useState } from "react";
import { obtenerSeguridad } from "./seguridad-api";
import type { HechosSeguridad } from "./seguridad-api";

type Vista =
  | { tipo: "cargando" }
  | { tipo: "error" }
  | { tipo: "listo"; hechos: HechosSeguridad };

function Lista({ titulo, items }: { titulo: string; items: string[] }): JSX.Element {
  return (
    <section className="seguridad-bloque" aria-label={titulo}>
      <h2>{titulo}</h2>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function Hechos({ hechos }: { hechos: HechosSeguridad }): JSX.Element {
  return (
    <>
      <p className="seguridad-declaracion">{hechos.declaracion}</p>
      <section className="seguridad-bloque" aria-label="Acceso y sesiones">
        <h2>Acceso y sesiones</h2>
        <ul>
          <li>Las contraseñas se guardan con {hechos.hash_contrasenas}; nunca en texto plano.</li>
          <li>La sesión vence a los {hechos.access_token_min} minutos.</li>
          <li>
            {hechos.refresh_rotativo
              ? "La renovación de sesión rota el código en cada uso."
              : "La renovación de sesión no rota el código."}
          </li>
        </ul>
      </section>
      <section className="seguridad-bloque" aria-label="Mensajes">
        <h2>Mensajes a pacientes</h2>
        <ul>
          <li>
            {hechos.whatsapp_modo === "mock"
              ? "WhatsApp funciona en modo de prueba: no se envía ningún mensaje real."
              : "WhatsApp real: se envían mensajes a los pacientes."}
          </li>
          {hechos.whatsapp_sin_datos_clinicos && (
            <li>Los mensajes nunca incluyen datos clínicos.</li>
          )}
          <li>
            {hechos.google_calendar_habilitado
              ? "Google Calendar tiene credenciales configuradas. "
              : "Google Calendar no está configurado. "}
            {hechos.google_calendar_nota}
          </li>
        </ul>
      </section>
      <Lista titulo="Qué queda registrado" items={hechos.auditoria} />
      <Lista titulo="Respaldos" items={hechos.respaldos} />
      <section className="seguridad-bloque seguridad-pendiente" aria-label="Pendiente para producción">
        <h2>Pendiente para producción</h2>
        <p>{hechos.cifrado}</p>
      </section>
    </>
  );
}

/** Página pública de seguridad: todo sale de GET /seguridad; sin backend no afirma nada. */
export function Seguridad(): JSX.Element {
  const [vista, setVista] = useState<Vista>({ tipo: "cargando" });

  useEffect(() => {
    let vivo = true;
    void obtenerSeguridad().then((hechos) => {
      if (vivo) setVista(hechos === null ? { tipo: "error" } : { tipo: "listo", hechos });
    });
    return (): void => {
      vivo = false;
    };
  }, []);

  return (
    <section className="seguridad">
      <h1>Cómo cuidamos la información</h1>
      {vista.tipo === "cargando" && <p>Cargando…</p>}
      {vista.tipo === "error" && (
        <p role="alert">No pudimos cargar la información de seguridad. Probá de nuevo en unos minutos.</p>
      )}
      {vista.tipo === "listo" && <Hechos hechos={vista.hechos} />}
    </section>
  );
}
