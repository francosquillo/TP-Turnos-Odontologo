import { useState } from "react";
import type { FormEvent } from "react";
import { apiUrl } from "../shared/api-client";

interface Hueco {
  inicio: string;
  fin: string;
}

interface ReservaExito {
  turno_id: number;
  estado: string;
  token: string;
  expira_en: string;
}

function etiquetaHora(iso: string): string {
  return new Date(iso).toISOString().slice(11, 16);
}

function diaSiguiente(dia: string): string {
  const [a, m, d] = dia.split("-").map(Number);
  const fecha = new Date(Date.UTC(a, m - 1, d + 1));
  return fecha.toISOString().slice(0, 10);
}

function esErrorConAlternativas(valor: unknown): valor is { alternativas: Hueco[] } {
  if (typeof valor !== "object" || valor === null) return false;
  return Array.isArray((valor as Record<string, unknown>)["alternativas"]);
}

/** Reserva online C-05: 3 pasos + 409 con re-oferta (fetch publico, sin Bearer). */
export function Reservas(props: { alConfirmar?: (token: string) => void }): JSX.Element {
  const [profesionalId, setProfesionalId] = useState<string>("");
  const [sillonId, setSillonId] = useState<string>("1");
  const [dia, setDia] = useState<string>("");
  const [huecos, setHuecos] = useState<Hueco[] | null>(null);
  const [buscando, setBuscando] = useState<boolean>(false);
  const [huecoElegido, setHuecoElegido] = useState<Hueco | null>(null);
  const [nombre, setNombre] = useState<string>("");
  const [telefono, setTelefono] = useState<string>("");
  const [alternativas, setAlternativas] = useState<Hueco[] | null>(null);
  const [exito, setExito] = useState<ReservaExito | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  const formularioCompleto =
    huecoElegido !== null &&
    nombre.trim().length >= 2 &&
    telefono.replace(/\D/g, "").length >= 8;

  async function buscar(evento: FormEvent): Promise<void> {
    evento.preventDefault();
    setBuscando(true);
    setError(null);
    setAlternativas(null);
    try {
      const params = new URLSearchParams({
        profesional_id: profesionalId,
        desde: `${dia}T00:00:00-03:00`,
        hasta: `${diaSiguiente(dia)}T00:00:00-03:00`,
      });
      const respuesta = await fetch(apiUrl(`/disponibilidad?${params.toString()}`));
      if (!respuesta.ok) throw new Error(`la API respondió ${respuesta.status}`);
      const cuerpo: unknown = await respuesta.json();
      if (!Array.isArray(cuerpo)) throw new Error("respuesta inesperada");
      setHuecos(cuerpo as Hueco[]);
      setHuecoElegido(null);
    } catch {
      setError("No se pudo cargar la disponibilidad, intentá de nuevo.");
    } finally {
      setBuscando(false);
    }
  }

  async function reservar(evento: FormEvent): Promise<void> {
    evento.preventDefault();
    if (huecoElegido === null || enviando) return;
    setEnviando(true);
    setError(null);
    try {
      const respuesta = await fetch(apiUrl("/reservas"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profesional_id: Number(profesionalId),
          sillon_id: Number(sillonId),
          inicio: huecoElegido.inicio,
          fin: huecoElegido.fin,
          nombre: nombre.trim(),
          telefono,
        }),
      });
      const cuerpo: unknown = await respuesta.json();
      if (respuesta.status === 409 && esErrorConAlternativas(cuerpo)) {
        setAlternativas(cuerpo.alternativas);
        return;
      }
      if (!respuesta.ok) throw new Error(`la API respondió ${respuesta.status}`);
      setExito(cuerpo as ReservaExito);
      setAlternativas(null);
    } catch {
      setError("No se pudo crear la reserva, intentá de nuevo.");
    } finally {
      setEnviando(false);
    }
  }

  if (exito !== null) {
    return (
      <section>
        <h1>¡Reserva creada!</h1>
        <p>Revisá tu WhatsApp: te enviamos el link de confirmación.</p>
        <p>
          Link de demo: <a href={`/confirmar/${exito.token}`}>{`/confirmar/${exito.token}`}</a>
        </p>
        {props.alConfirmar !== undefined && (
          <button type="button" onClick={(): void => props.alConfirmar?.(exito.token)}>
            Confirmar ahora
          </button>
        )}
      </section>
    );
  }

  return (
    <section>
      <h1>Reservá tu turno</h1>
      <form onSubmit={(e): Promise<void> => buscar(e)}>
        <label htmlFor="reserva-profesional">Profesional (ID)</label>
        <input
          id="reserva-profesional"
          inputMode="numeric"
          value={profesionalId}
          onChange={(e): void => setProfesionalId(e.target.value)}
          required
        />
        <label htmlFor="reserva-sillon">Sillón (ID)</label>
        <input
          id="reserva-sillon"
          inputMode="numeric"
          value={sillonId}
          onChange={(e): void => setSillonId(e.target.value)}
          required
        />
        <label htmlFor="reserva-dia">Día</label>
        <input
          id="reserva-dia"
          type="date"
          value={dia}
          onChange={(e): void => setDia(e.target.value)}
          required
        />
        <button type="submit" disabled={buscando || profesionalId === "" || dia === ""}>
          Buscar huecos
        </button>
      </form>

      {huecos !== null && huecos.length === 0 && <p>No hay huecos ese día.</p>}
      {huecos !== null && huecos.length > 0 && (
        <div>
          <h2>Elegí el horario</h2>
          {huecos.map((h) => (
            <button
              key={h.inicio}
              type="button"
              aria-pressed={huecoElegido?.inicio === h.inicio}
              onClick={(): void => {
                setHuecoElegido(h);
                setAlternativas(null);
              }}
            >
              {`${etiquetaHora(h.inicio)} – ${etiquetaHora(h.fin)}`}
            </button>
          ))}
        </div>
      )}

      {alternativas !== null && alternativas.length > 0 && (
        <div>
          <p>Ese hueco se acaba de ocupar. Te ofrecemos estas alternativas:</p>
          {alternativas.map((h) => (
            <button
              key={h.inicio}
              type="button"
              aria-pressed={huecoElegido?.inicio === h.inicio}
              onClick={(): void => setHuecoElegido(h)}
            >
              {`${etiquetaHora(h.inicio)} – ${etiquetaHora(h.fin)}`}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={(e): Promise<void> => reservar(e)}>
        <label htmlFor="reserva-nombre">Nombre</label>
        <input
          id="reserva-nombre"
          value={nombre}
          onChange={(e): void => setNombre(e.target.value)}
          required
          minLength={2}
        />
        <label htmlFor="reserva-telefono">Teléfono</label>
        <input
          id="reserva-telefono"
          inputMode="tel"
          value={telefono}
          onChange={(e): void => setTelefono(e.target.value)}
          required
        />
        <button type="submit" disabled={!formularioCompleto || enviando}>
          Confirmar reserva
        </button>
      </form>

      {error !== null && <p role="alert">{error}</p>}
    </section>
  );
}
