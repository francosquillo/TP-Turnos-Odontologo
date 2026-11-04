import { useEffect, useState } from "react";
import { aceptarOferta, rechazarOferta, verOferta } from "../features/lista-espera/api";
import type { Alternativa, ResultadoPublico } from "../features/lista-espera/api";
import { Countdown, useAhoraMs } from "../features/lista-espera/Countdown";
import { formatoFechaHora, segundosRestantes } from "../features/lista-espera/tipos";
import type { OfertaPublica } from "../features/lista-espera/tipos";

const TELEFONO: string =
  (import.meta.env["VITE_CONSULTORIO_TEL"] as string | undefined) ?? "+54 11 4000-0000";

type Vista =
  | { tipo: "cargando" }
  | { tipo: "oferta"; oferta: OfertaPublica }
  | { tipo: "aceptada" }
  | { tipo: "rechazada" }
  | { tipo: "no-existe" }
  | { tipo: "no-disponible" }
  | { tipo: "resuelta" }
  | { tipo: "vencida" }
  | { tipo: "hueco-ocupado"; alternativas: Alternativa[] }
  | { tipo: "error" };

interface BannerProps {
  variante: "error" | "warning";
  titulo: string;
  children: React.ReactNode;
}

function Banner({ variante, titulo, children }: BannerProps): JSX.Element {
  return (
    <div className={`banner banner-${variante}`} role="alert">
      <span className="banner-icon" aria-hidden="true">
        <span>!</span>
      </span>
      <div>
        <strong>{titulo}</strong>
        {children}
      </div>
    </div>
  );
}

function vistaDeResultado(resultado: ResultadoPublico, ok: Vista): Vista {
  return resultado.tipo === "ok" ? ok : resultado;
}

/** Página pública `/lista-espera/:token`: aceptar o rechazar una oferta de turno (sin Bearer). */
export function OfertaEspera(props: { token: string }): JSX.Element {
  const [vista, setVista] = useState<Vista>({ tipo: "cargando" });
  const [enviando, setEnviando] = useState<boolean>(false);
  const ahoraMs = useAhoraMs(vista.tipo === "oferta");

  useEffect(() => {
    let vivo = true;
    verOferta(props.token).then((resultado) => {
      if (!vivo) return;
      setVista(resultado.tipo === "ok" ? { tipo: "oferta", oferta: resultado.oferta } : resultado);
    });
    return (): void => {
      vivo = false;
    };
  }, [props.token]);

  async function responder(accion: "aceptar" | "rechazar"): Promise<void> {
    setEnviando(true);
    const resultado = await (accion === "aceptar" ? aceptarOferta : rechazarOferta)(props.token);
    setVista(vistaDeResultado(resultado, { tipo: accion === "aceptar" ? "aceptada" : "rechazada" }));
    setEnviando(false);
  }

  const llamar = <>Llamá al consultorio al {TELEFONO}.</>;

  return (
    <section className="oferta card wrap-sm" style={{ padding: "var(--space-6)", marginTop: "var(--space-6)" }}>
      {vista.tipo === "cargando" && <p>Cargando…</p>}
      {vista.tipo === "oferta" && (
        <>
          <h1>Se liberó un turno para vos</h1>
          <p>
            Hola, {vista.oferta.nombre_pila}. Hay un turno el {formatoFechaHora(vista.oferta.inicio)}.
          </p>
          <p className="muted">Tenés para responder</p>
          <p className="tiempo">
            <Countdown expiraEn={vista.oferta.oferta_expira_en} ahoraMs={ahoraMs} />
          </p>
          <div className="row">
            <button
              className="btn btn-primary"
              type="button"
              disabled={enviando || segundosRestantes(vista.oferta.oferta_expira_en, ahoraMs) === 0}
              onClick={(): void => void responder("aceptar")}
            >
              Aceptar turno
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              disabled={enviando}
              onClick={(): void => void responder("rechazar")}
            >
              No puedo
            </button>
          </div>
        </>
      )}
      {vista.tipo === "aceptada" && (
        <div className="banner banner-success" role="status">
          <span className="banner-icon" aria-hidden="true">
            <span>✓</span>
          </span>
          <div>
            <strong>¡Turno confirmado!</strong>Te esperamos. Si algo cambia, avisanos al {TELEFONO}.
          </div>
        </div>
      )}
      {vista.tipo === "rechazada" && (
        <div className="banner banner-success" role="status">
          <span className="banner-icon" aria-hidden="true">
            <span>✓</span>
          </span>
          <div>
            <strong>Gracias por avisar</strong>Le ofrecemos el turno a la siguiente persona de la lista.
          </div>
        </div>
      )}
      {vista.tipo === "no-existe" && (
        <Banner variante="error" titulo="La oferta ya no existe">
          El link no es válido. {llamar}
        </Banner>
      )}
      {vista.tipo === "no-disponible" && (
        <Banner variante="error" titulo="La oferta ya no está disponible">
          Venció o ya fue respondida. {llamar}
        </Banner>
      )}
      {vista.tipo === "resuelta" && (
        <Banner variante="warning" titulo="Alguien más ya respondió">
          Esta oferta ya fue aceptada o rechazada.
        </Banner>
      )}
      {vista.tipo === "vencida" && (
        <Banner variante="error" titulo="La oferta venció">
          Pasaron las 2 horas para responder. {llamar}
        </Banner>
      )}
      {vista.tipo === "hueco-ocupado" && (
        <>
          <Banner variante="warning" titulo="Ese horario ya fue ocupado">
            Alguien tomó el turno antes. {llamar}
          </Banner>
          {vista.alternativas.length > 0 && (
            <>
              <p className="muted">Otros horarios disponibles</p>
              <ul>
                {vista.alternativas.map((a) => (
                  <li key={a.inicio}>{formatoFechaHora(a.inicio)}</li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
      {vista.tipo === "error" && (
        <Banner variante="error" titulo="No pudimos procesar tu respuesta">
          Probá de nuevo en unos minutos. {llamar}
        </Banner>
      )}
    </section>
  );
}
