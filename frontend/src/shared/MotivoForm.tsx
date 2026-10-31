import { useState } from "react";
import type { FormEvent } from "react";

interface Props {
  /** Prefijo unico para el id del campo. */
  idBase: string;
  /** Etiqueta visible del campo (por ejemplo "Motivo del rechazo"). */
  etiqueta: string;
  textoBoton: string;
  /** Operaciones destructivas usan el boton de peligro. */
  peligro?: boolean;
  alConfirmar: (motivo: string) => Promise<void>;
  alCancelar: () => void;
}

/** Motivo obligatorio de una operacion (rechazo, baja, anulacion). Si esta vacio no se envia
 * y se indica que es obligatorio. El motivo viaja en el cuerpo y no se escribe en consola. */
export function MotivoForm({
  idBase,
  etiqueta,
  textoBoton,
  peligro = false,
  alConfirmar,
  alCancelar,
}: Props): JSX.Element {
  const [motivo, setMotivo] = useState<string>("");
  const [faltante, setFaltante] = useState<boolean>(false);
  const [enviando, setEnviando] = useState<boolean>(false);

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    const limpio = motivo.trim();
    if (limpio === "") {
      setFaltante(true);
      return;
    }
    if (enviando) return;
    setFaltante(false);
    setEnviando(true);
    try {
      await alConfirmar(limpio);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form
      className="motivo-form"
      aria-label={textoBoton}
      noValidate
      onSubmit={(e): void => {
        void enviar(e);
      }}
    >
      <div className="field">
        <label htmlFor={`${idBase}-motivo`}>{etiqueta}</label>
        <input
          id={`${idBase}-motivo`}
          className="input"
          type="text"
          maxLength={500}
          value={motivo}
          aria-invalid={faltante}
          aria-describedby={faltante ? `${idBase}-motivo-error` : undefined}
          onChange={(e): void => setMotivo(e.target.value)}
        />
        {faltante && (
          <span id={`${idBase}-motivo-error`} role="alert" className="motivo-error">
            El motivo es obligatorio.
          </span>
        )}
      </div>
      <div className="motivo-acciones">
        <button type="submit" className={peligro ? "btn btn-danger btn-sm" : "btn btn-primary btn-sm"} disabled={enviando}>
          {textoBoton}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
