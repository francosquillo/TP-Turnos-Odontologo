/** Landing publica C-05: entrada sin login (links a reservas y seguridad). */
export function Inicio(props: { alNavegar: (destino: string) => void }): JSX.Element {
  return (
    <section>
      <h1>Turnos odontológicos</h1>
      <p>Reservá tu turno online, sin cuenta y en 1 minuto.</p>
      <button
        type="button"
        onClick={(): void => props.alNavegar("reservas")}
      >
        Reservar turno
      </button>{" "}
      <button
        type="button"
        onClick={(): void => props.alNavegar("seguridad")}
      >
        Seguridad
      </button>
    </section>
  );
}
