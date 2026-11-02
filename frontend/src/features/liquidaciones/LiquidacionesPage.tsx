import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../shared/api-client";
import { formatearMoneda } from "../../shared/moneda";
import { listarLiquidaciones, listarObrasSociales, obtenerLiquidacion } from "./api";
import { guardarArchivo } from "./descarga";
import type { GuardarArchivo } from "./descarga";
import { GenerarForm } from "./GenerarForm";
import { LiquidacionDetalleVista } from "./LiquidacionDetalleVista";
import { ETIQUETA_ESTADO, periodoATexto } from "./tipos";
import type { Liquidacion, LiquidacionDetalle, ObraSocial } from "./tipos";

interface Props {
  /** `admin` opera; `odontologo` ve solo sus filas y en modo lectura. */
  rol: "admin" | "odontologo";
  /** Entrega del archivo exportado; se puede reemplazar en tests. */
  guardar?: GuardarArchivo;
}

type Carga =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "lista"; liquidaciones: Liquidacion[]; obras: ObraSocial[] };

const mensajeDe = (fallo: unknown): string =>
  fallo instanceof ApiError ? fallo.message : "No se pudieron cargar las liquidaciones";

/** Lista, generacion y detalle de liquidaciones a obras sociales (C-11). Lee la lista y, para el
 * admin, el catalogo de obras sociales a la vez (`Promise.all`). */
export function LiquidacionesPage({ rol, guardar = guardarArchivo }: Props): JSX.Element {
  const [carga, setCarga] = useState<Carga>({ tipo: "cargando" });
  const [detalle, setDetalle] = useState<LiquidacionDetalle | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cargar = useCallback(async (): Promise<void> => {
    try {
      const [liquidaciones, obras] = await Promise.all([
        listarLiquidaciones(),
        rol === "admin" ? listarObrasSociales() : Promise.resolve<ObraSocial[]>([]),
      ]);
      setCarga({ tipo: "lista", liquidaciones, obras });
    } catch (fallo) {
      setCarga({ tipo: "error", mensaje: mensajeDe(fallo) });
    }
  }, [rol]);

  useEffect(() => {
    setCarga({ tipo: "cargando" });
    void cargar();
  }, [cargar]);

  async function ver(id: number): Promise<void> {
    setAviso(null);
    try {
      setDetalle(await obtenerLiquidacion(id));
    } catch (fallo) {
      setAviso(mensajeDe(fallo));
    }
  }

  function alActualizada(nuevo: LiquidacionDetalle): void {
    setDetalle(nuevo);
    void cargar();
  }

  function alDescartada(): void {
    setDetalle(null);
    void cargar();
  }

  if (carga.tipo === "cargando") {
    return (
      <section className="liquidaciones" aria-label="Liquidaciones">
        <p className="muted">Cargando liquidaciones…</p>
      </section>
    );
  }

  if (carga.tipo === "error") {
    return (
      <section className="liquidaciones" aria-label="Liquidaciones">
        <p role="alert" className="banner banner-error">
          {carga.mensaje}
        </p>
      </section>
    );
  }

  return (
    <section className="liquidaciones" aria-label="Liquidaciones">
      <h2>Liquidaciones a obras sociales</h2>
      <p className="muted">Datos ficticios de demostración.</p>

      {rol === "admin" && <GenerarForm obras={carga.obras} alGenerada={alActualizada} />}

      {carga.liquidaciones.length === 0 ? (
        <p className="muted">Todavía no hay liquidaciones.</p>
      ) : (
        <ul className="liq-lista" aria-label="Liquidaciones">
          {carga.liquidaciones.map((l) => (
            <li key={l.id} data-estado={l.estado}>
              <span className="titulo">
                {l.obra_social} · período {periodoATexto(l.periodo)}
              </span>
              <span className="muted">Estado: {ETIQUETA_ESTADO[l.estado]}</span>
              <span className="pres-importe">{formatearMoneda(l.total)}</span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                aria-label={`Ver liquidación ${l.id}`}
                onClick={(): void => void ver(l.id)}
              >
                Ver
              </button>
            </li>
          ))}
        </ul>
      )}

      {aviso !== null && (
        <p role="alert" className="banner banner-error">
          {aviso}
        </p>
      )}

      {detalle !== null && (
        <LiquidacionDetalleVista
          key={detalle.id}
          detalle={detalle}
          rol={rol}
          guardar={guardar}
          alActualizada={alActualizada}
          alDescartada={alDescartada}
        />
      )}
    </section>
  );
}
