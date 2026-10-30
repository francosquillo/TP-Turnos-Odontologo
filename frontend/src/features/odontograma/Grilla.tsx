import { useMemo } from "react";
import { CARAS, CUADRANTES, estadoVigente, etiquetaCara } from "./tipos";
import type { Hallazgo } from "./tipos";

interface Props {
  /** Todos los hallazgos de la historia (los anulados se ignoran al derivar el estado). */
  hallazgos: readonly Hallazgo[];
  /** codigo de estado → nombre legible del catalogo. */
  nombres: Readonly<Record<string, string>>;
  seleccionada: number | null;
  alSeleccionar: (pieza: number) => void;
}

function porPieza(hallazgos: readonly Hallazgo[]): Map<number, Hallazgo[]> {
  const mapa = new Map<number, Hallazgo[]>();
  for (const h of hallazgos) {
    const lista = mapa.get(h.pieza_fdi) ?? [];
    lista.push(h);
    mapa.set(h.pieza_fdi, lista);
  }
  return mapa;
}

/** "Obturación (Oclusal), Caries (Mesial)" o "" sin registros activos. */
function resumen(pieza: number, hallazgos: readonly Hallazgo[], nombres: Readonly<Record<string, string>>): string {
  const vigente = estadoVigente(hallazgos);
  return CARAS.filter((cara) => vigente.has(cara))
    .map((cara) => {
      const estado = vigente.get(cara)?.estado ?? "";
      return `${nombres[estado] ?? estado} (${etiquetaCara(pieza, cara)})`;
    })
    .join(", ");
}

/** Codigo del estado que da color a la celda: la pieza completa manda, si no la primera cara. */
function estadoDominante(hallazgos: readonly Hallazgo[]): string {
  const vigente = estadoVigente(hallazgos);
  const dominante = vigente.get("pieza_completa") ?? CARAS.map((c) => vigente.get(c)).find((h) => h !== undefined);
  return dominante?.estado ?? "ninguno";
}

export function Grilla({ hallazgos, nombres, seleccionada, alSeleccionar }: Props): JSX.Element {
  const agrupados = useMemo(() => porPieza(hallazgos), [hallazgos]);

  return (
    <div className="odonto-grilla">
      {CUADRANTES.map((cuadrante) => (
        <div key={cuadrante.id} role="group" aria-label={cuadrante.nombre} className="odonto-cuadrante">
          <p className="odonto-cuadrante-titulo">{cuadrante.nombre}</p>
          <div className="odonto-piezas">
            {cuadrante.piezas.map((pieza) => {
              const propios = agrupados.get(pieza) ?? [];
              const texto = resumen(pieza, propios, nombres);
              return (
                <button
                  key={pieza}
                  type="button"
                  className="odonto-pieza"
                  data-estado={estadoDominante(propios)}
                  aria-pressed={seleccionada === pieza}
                  aria-label={`Pieza ${pieza}: ${texto === "" ? "sin registros" : texto}`}
                  onClick={(): void => alSeleccionar(pieza)}
                >
                  <span className="odonto-pieza-numero">{pieza}</span>
                  <span className="odonto-pieza-estado">{texto === "" ? "Sin registros" : texto}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
