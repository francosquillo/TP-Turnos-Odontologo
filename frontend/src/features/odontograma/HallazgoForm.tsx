import { useState } from "react";
import type { FormEvent } from "react";
import { alcanceDe, carasPermitidas, etiquetaCara } from "./tipos";
import type { Cara, Catalogo, DatosHallazgo } from "./tipos";

interface Props {
  /** Prefijo unico para los ids de los campos (varios formularios conviven en pantalla). */
  idBase: string;
  pieza: number;
  catalogo: Catalogo;
  /** Valores de partida (correccion); por defecto el primer estado y la primera cara. */
  inicial?: { estado: string; cara: Cara };
  /** Una correccion exige el motivo del cambio. */
  pedirMotivo: boolean;
  etiquetaBoton: string;
  alEnviar: (datos: DatosHallazgo, motivo: string) => Promise<void>;
  alCancelar?: () => void;
}

export function HallazgoForm({
  idBase,
  pieza,
  catalogo,
  inicial,
  pedirMotivo,
  etiquetaBoton,
  alEnviar,
  alCancelar,
}: Props): JSX.Element {
  const [estado, setEstado] = useState<string>(inicial?.estado ?? catalogo.estados[0]?.codigo ?? "");
  const [caraElegida, setCaraElegida] = useState<Cara>(inicial?.cara ?? "oclusal");
  const [motivo, setMotivo] = useState<string>("");
  const [enviando, setEnviando] = useState<boolean>(false);

  // Derivado en render: si la cara elegida deja de ser valida para el estado, se usa la primera.
  const caras = carasPermitidas(pieza, alcanceDe(catalogo, estado));
  const cara: Cara = caras.includes(caraElegida) ? caraElegida : (caras[0] ?? "pieza_completa");
  const motivoLimpio = motivo.trim();
  const incompleto = estado === "" || (pedirMotivo && motivoLimpio === "");

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (incompleto || enviando) return;
    setEnviando(true);
    try {
      await alEnviar({ pieza_fdi: pieza, cara, estado }, motivoLimpio);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form
      className="odonto-form"
      aria-label={etiquetaBoton}
      onSubmit={(e): void => {
        void enviar(e);
      }}
    >
      <div className="row">
        <div className="field">
          <label htmlFor={`${idBase}-estado`}>Estado</label>
          <select
            id={`${idBase}-estado`}
            className="input"
            value={estado}
            onChange={(e): void => setEstado(e.target.value)}
          >
            {catalogo.estados.map((e) => (
              <option key={e.codigo} value={e.codigo}>
                {e.nombre}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${idBase}-cara`}>Cara</label>
          <select
            id={`${idBase}-cara`}
            className="input"
            value={cara}
            onChange={(e): void => setCaraElegida(e.target.value as Cara)}
          >
            {caras.map((c) => (
              <option key={c} value={c}>
                {etiquetaCara(pieza, c)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {pedirMotivo && (
        <div className="field">
          <label htmlFor={`${idBase}-motivo`}>Motivo de la corrección</label>
          <input
            id={`${idBase}-motivo`}
            className="input"
            type="text"
            maxLength={500}
            value={motivo}
            onChange={(e): void => setMotivo(e.target.value)}
          />
        </div>
      )}
      <div className="odonto-acciones">
        <button type="submit" className="btn btn-primary" disabled={incompleto || enviando}>
          {etiquetaBoton}
        </button>
        {alCancelar !== undefined && (
          <button type="button" className="btn btn-ghost" onClick={alCancelar}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
