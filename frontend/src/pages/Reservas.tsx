import { useState } from "react";
import type { FormEvent } from "react";
import { apiUrl } from "../shared/api-client";
import { horaAR } from "../shared/fecha";

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
  return horaAR(iso);
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
      <section className="card wrap-sm" style={{ textAlign: "center", padding: "var(--space-6)" }}>
        <div style={{ fontSize: "2.5rem", marginBottom: "var(--space-2)" }}>✅</div>
        <h1 style={{ color: "var(--color-primary)", marginBottom: "var(--space-2)" }}>¡Reserva creada!</h1>
        <p style={{ fontSize: "var(--text-lg)", marginBottom: "var(--space-3)" }}>
          Revisá tu WhatsApp: te enviamos el link de confirmación.
        </p>
        <div className="banner banner-success" style={{ justifyContent: "center", marginBottom: "var(--space-4)" }}>
          <p style={{ margin: 0, wordBreak: "break-all" }}>
            Link de demo: <a href={`/confirmar/${exito.token}`}>{`/confirmar/${exito.token}`}</a>
          </p>
        </div>
        {props.alConfirmar !== undefined && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={(): void => props.alConfirmar?.(exito.token)}
          >
            Confirmar ahora
          </button>
        )}
      </section>
    );
  }

  return (
    <section className="wrap-sm" style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      <div>
        <h1 style={{ marginBottom: "var(--space-1)" }}>Reservá tu turno</h1>
        <p className="muted" style={{ margin: 0 }}>Completá los pasos para agendar tu consulta odontológica.</p>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: "var(--space-3)", color: "var(--color-primary)" }}>1. Elegí profesional y fecha</h3>
        <form onSubmit={(e): Promise<void> => buscar(e)}>
          <div className="field">
            <label htmlFor="reserva-profesional">Profesional (ID)</label>
            <input
              id="reserva-profesional"
              className="input"
              inputMode="numeric"
              placeholder="Ej. 1"
              value={profesionalId}
              onChange={(e): void => setProfesionalId(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="reserva-sillon">Sillón (ID)</label>
            <input
              id="reserva-sillon"
              className="input"
              inputMode="numeric"
              value={sillonId}
              onChange={(e): void => setSillonId(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="reserva-dia">Día</label>
            <input
              id="reserva-dia"
              className="input"
              type="date"
              value={dia}
              onChange={(e): void => setDia(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%" }}
            disabled={buscando || profesionalId === "" || dia === ""}
          >
            {buscando ? "Buscando..." : "Buscar huecos"}
          </button>
        </form>
      </div>

      {huecos !== null && huecos.length === 0 && (
        <div className="banner banner-warning">
          <p style={{ margin: 0 }}>No hay huecos ese día.</p>
        </div>
      )}

      {huecos !== null && huecos.length > 0 && (
        <div className="card">
          <h2 style={{ fontSize: "var(--text-lg)", marginBottom: "var(--space-3)", color: "var(--color-primary)" }}>
            2. Elegí el horario
          </h2>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
            {huecos.map((h) => {
              const seleccionado = huecoElegido?.inicio === h.inicio;
              return (
                <button
                  key={h.inicio}
                  type="button"
                  className={`btn ${seleccionado ? "btn-primary" : "btn-secondary"} btn-sm`}
                  aria-pressed={seleccionado}
                  onClick={(): void => {
                    setHuecoElegido(h);
                    setAlternativas(null);
                  }}
                >
                  {`${etiquetaHora(h.inicio)} – ${etiquetaHora(h.fin)}`}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {alternativas !== null && alternativas.length > 0 && (
        <div className="card" style={{ borderColor: "var(--color-warning-text)" }}>
          <p className="error-msg" style={{ marginTop: 0 }}>
            Ese hueco se acaba de ocupar. Te ofrecemos estas alternativas:
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
            {alternativas.map((h) => {
              const seleccionado = huecoElegido?.inicio === h.inicio;
              return (
                <button
                  key={h.inicio}
                  type="button"
                  className={`btn ${seleccionado ? "btn-primary" : "btn-secondary"} btn-sm`}
                  aria-pressed={seleccionado}
                  onClick={(): void => setHuecoElegido(h)}
                >
                  {`${etiquetaHora(h.inicio)} – ${etiquetaHora(h.fin)}`}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginBottom: "var(--space-3)", color: "var(--color-primary)" }}>3. Tus datos de contacto</h3>
        <form onSubmit={(e): Promise<void> => reservar(e)}>
          <div className="field">
            <label htmlFor="reserva-nombre">Nombre</label>
            <input
              id="reserva-nombre"
              className="input"
              placeholder="Nombre y apellido"
              value={nombre}
              onChange={(e): void => setNombre(e.target.value)}
              required
              minLength={2}
            />
          </div>

          <div className="field">
            <label htmlFor="reserva-telefono">Teléfono</label>
            <input
              id="reserva-telefono"
              className="input"
              inputMode="tel"
              placeholder="Ej. 11 5555-5555"
              value={telefono}
              onChange={(e): void => setTelefono(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", marginTop: "var(--space-2)" }}
            disabled={!formularioCompleto || enviando}
          >
            {enviando ? "Confirmando..." : "Confirmar reserva"}
          </button>
        </form>
      </div>

      {error !== null && (
        <div className="banner banner-error">
          <p role="alert" style={{ margin: 0 }}>{error}</p>
        </div>
      )}
    </section>
  );
}
