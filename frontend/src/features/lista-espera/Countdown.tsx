import { useEffect, useState } from "react";
import { SEGUNDOS_URGENTE, formatearCuenta, segundosRestantes } from "./tipos";

/** Reloj compartido: re-render cada segundo; el valor se DERIVA en render. */
export function useAhoraMs(activo: boolean): number {
  const [ahora, setAhora] = useState<number>(() => Date.now());
  useEffect(() => {
    if (!activo) return;
    setAhora(Date.now());
    const id = setInterval((): void => setAhora(Date.now()), 1000);
    return (): void => clearInterval(id);
  }, [activo]);
  return ahora;
}

interface Props {
  expiraEn: string;
  ahoraMs: number;
}

/** Countdown derivado de `oferta_expira_en`; al llegar a 0 dice "Oferta vencida". */
export function Countdown({ expiraEn, ahoraMs }: Props): JSX.Element {
  const restantes = segundosRestantes(expiraEn, ahoraMs);
  if (restantes === 0) {
    return (
      <span className="countdown" data-vencido="true">
        Oferta vencida
      </span>
    );
  }
  return (
    <span className="countdown" data-urgente={restantes < SEGUNDOS_URGENTE ? "true" : undefined}>
      {formatearCuenta(restantes)}
    </span>
  );
}
