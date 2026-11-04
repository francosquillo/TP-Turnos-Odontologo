/** Landing publica C-05: entrada sin login (links a reservas y seguridad). */
export function Inicio(props: { alNavegar: (destino: string) => void }): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <section className="card" style={{ padding: "var(--space-6)", textAlign: "center" }}>
        <h1 style={{ fontSize: "var(--text-2xl)", color: "var(--color-primary)", marginBottom: "var(--space-2)" }}>
          Turnos odontológicos
        </h1>
        <p className="muted" style={{ fontSize: "var(--text-lg)", maxWidth: "600px", margin: "0 auto var(--space-5)" }}>
          Reservá tu turno online, sin cuenta y en 1 minuto. Atención profesional, turnos puntuales y recordatorios automáticos.
        </p>
        <div className="row" style={{ justifyContent: "center", gap: "var(--space-3)" }}>
          <button
            type="button"
            className="btn btn-primary"
            style={{ fontSize: "var(--text-md)", padding: "0 var(--space-5)" }}
            onClick={(): void => props.alNavegar("reservas")}
          >
            Reservar turno
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={(): void => props.alNavegar("seguridad")}
          >
            Seguridad
          </button>
        </div>
      </section>

      <section className="grid">
        <div className="card">
          <h3 style={{ color: "var(--color-primary)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span>📅</span> Reserva 24/7
          </h3>
          <p className="muted" style={{ margin: 0 }}>
            Elegí el profesional y el horario que mejor te quede desde cualquier dispositivo móvil o computadora.
          </p>
        </div>

        <div className="card">
          <h3 style={{ color: "var(--color-primary)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span>⏳</span> Lista de espera inteligente
          </h3>
          <p className="muted" style={{ margin: 0 }}>
            Si se libera un hueco antes de tu fecha, te avisamos de inmediato para que puedas adelantarlo.
          </p>
        </div>

        <div className="card">
          <h3 style={{ color: "var(--color-primary)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span>🔒</span> Privacidad médica
          </h3>
          <p className="muted" style={{ margin: 0 }}>
            Cumplimos con estrictos estándares de seguridad y protección de datos para resguardar tu información clínica.
          </p>
        </div>
      </section>
    </div>
  );
}
