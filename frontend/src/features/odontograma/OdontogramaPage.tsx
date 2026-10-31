import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import {
  abrirHistoria,
  actualizarHistoria,
  buscarHistoria,
  corregirHallazgo,
  darDeBajaHallazgo,
  listarHallazgos,
  obtenerCatalogo,
  registrarHallazgo,
} from "./api";
import { AlergiasAviso } from "./AlergiasAviso";
import { Grilla } from "./Grilla";
import { PiezaDetalle } from "./PiezaDetalle";
import type { Catalogo, DatosHallazgo, Hallazgo, Historia } from "./tipos";

// C-09: los presupuestos se cargan bajo demanda y reciben los hallazgos ya cargados.
const PresupuestosPanel = lazy(() =>
  import("../presupuestos/PresupuestosPanel").then((m) => ({ default: m.PresupuestosPanel })),
);

interface Props {
  pacienteId: number;
  pacienteNombre: string;
  rol: "odontologo" | "secretaria";
  alVolver: () => void;
}

type Estado =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "sin-historia"; catalogo: Catalogo }
  | { tipo: "listo"; historia: Historia; catalogo: Catalogo; hallazgos: Hallazgo[] };

function mensajeDe(error: unknown): string {
  return error instanceof ApiError ? error.message : "No se pudo cargar el odontograma";
}

interface HistoriaPanelProps {
  historia: Historia;
  puedeEditar: boolean;
  alGuardar: (antecedentes: string, alergias: string) => Promise<void>;
}

function HistoriaPanel({ historia, puedeEditar, alGuardar }: HistoriaPanelProps): JSX.Element {
  const [antecedentes, setAntecedentes] = useState<string>(historia.antecedentes ?? "");
  const [alergias, setAlergias] = useState<string>(historia.alergias ?? "");
  const [error, setError] = useState<string | null>(null);

  if (!puedeEditar) {
    return (
      <section className="odonto-historia-form" aria-label="Antecedentes">
        <h3>Antecedentes</h3>
        <p>{historia.antecedentes ?? "Sin antecedentes cargados."}</p>
      </section>
    );
  }

  async function guardar(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    try {
      await alGuardar(antecedentes.trim(), alergias.trim());
    } catch (fallo) {
      setError(mensajeDe(fallo));
    }
  }

  return (
    <form
      className="odonto-form odonto-historia-form"
      aria-label="Historia clínica"
      onSubmit={(e): void => {
        void guardar(e);
      }}
    >
      <div className="field">
        <label htmlFor="hc-antecedentes">Antecedentes</label>
        <textarea
          id="hc-antecedentes"
          className="input"
          maxLength={10000}
          value={antecedentes}
          onChange={(e): void => setAntecedentes(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="hc-alergias">Alergias</label>
        <textarea
          id="hc-alergias"
          className="input"
          maxLength={2000}
          value={alergias}
          onChange={(e): void => setAlergias(e.target.value)}
        />
        <span className="muted">Si no tiene alergias, escribilo (por ejemplo: Sin alergias conocidas).</span>
      </div>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      <button type="submit" className="btn btn-primary">
        Guardar historia
      </button>
    </form>
  );
}

export function OdontogramaPage({ pacienteId, pacienteNombre, rol, alVolver }: Props): JSX.Element {
  const [estado, setEstado] = useState<Estado>({ tipo: "cargando" });
  const [pieza, setPieza] = useState<number | null>(null);
  const [avisoAlta, setAvisoAlta] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    setEstado({ tipo: "cargando" });
    setPieza(null);
    Promise.all([buscarHistoria(pacienteId), obtenerCatalogo()])
      .then(async ([historia, catalogo]): Promise<Estado> => {
        if (historia === null) return { tipo: "sin-historia", catalogo };
        const listado = await listarHallazgos(historia.id);
        return { tipo: "listo", historia, catalogo, hallazgos: listado.hallazgos };
      })
      .then((siguiente) => {
        if (vigente) setEstado(siguiente);
      })
      .catch((fallo: unknown) => {
        if (vigente) setEstado({ tipo: "error", mensaje: mensajeDe(fallo) });
      });
    return (): void => {
      vigente = false;
    };
  }, [pacienteId]);

  const nombres = useMemo<Record<string, string>>(() => {
    if (estado.tipo !== "listo" && estado.tipo !== "sin-historia") return {};
    return Object.fromEntries(estado.catalogo.estados.map((e) => [e.codigo, e.nombre]));
  }, [estado]);

  const recargar = useCallback(async (historia: Historia): Promise<void> => {
    const listado = await listarHallazgos(historia.id);
    setEstado((previo) =>
      previo.tipo === "listo" ? { ...previo, hallazgos: listado.hallazgos } : previo,
    );
  }, []);

  async function abrir(catalogo: Catalogo): Promise<void> {
    setAvisoAlta(null);
    try {
      const historia = await abrirHistoria(pacienteId, {});
      const listado = await listarHallazgos(historia.id);
      setEstado({ tipo: "listo", historia, catalogo, hallazgos: listado.hallazgos });
    } catch (fallo) {
      setAvisoAlta(mensajeDe(fallo));
    }
  }

  const encabezado = (
    <div className="odonto-cabecera">
      <h2>Odontograma · {pacienteNombre}</h2>
      <button type="button" className="btn btn-secondary btn-sm" onClick={alVolver}>
        Volver a la agenda
      </button>
    </div>
  );

  if (estado.tipo === "cargando") {
    return (
      <section className="odonto" aria-label="Odontograma">
        {encabezado}
        <p className="muted">Cargando historia clínica…</p>
      </section>
    );
  }

  if (estado.tipo === "error") {
    return (
      <section className="odonto" aria-label="Odontograma">
        {encabezado}
        <p role="alert" className="banner banner-error">
          {estado.mensaje}
        </p>
      </section>
    );
  }

  if (estado.tipo === "sin-historia") {
    return (
      <section className="odonto" aria-label="Odontograma">
        {encabezado}
        {rol === "odontologo" ? (
          <>
            <p>Este paciente todavía no tiene historia clínica.</p>
            {avisoAlta !== null && (
              <p role="alert" className="banner banner-error">
                {avisoAlta}
              </p>
            )}
            <button
              type="button"
              className="btn btn-primary"
              onClick={(): void => {
                void abrir(estado.catalogo);
              }}
            >
              Abrir historia
            </button>
          </>
        ) : (
          <p>El paciente no tiene historia clínica. La abre el odontólogo en su primera atención.</p>
        )}
      </section>
    );
  }

  const { historia, catalogo, hallazgos } = estado;

  async function guardarHistoria(antecedentes: string, alergias: string): Promise<void> {
    const actualizada = await actualizarHistoria(historia.id, { antecedentes, alergias });
    setEstado((previo) => (previo.tipo === "listo" ? { ...previo, historia: actualizada } : previo));
  }

  return (
    <section className="odonto" aria-label="Odontograma">
      {encabezado}
      <AlergiasAviso alergias={historia.alergias} />
      <HistoriaPanel
        key={historia.updated_at}
        historia={historia}
        puedeEditar={rol === "odontologo"}
        alGuardar={guardarHistoria}
      />
      <Grilla hallazgos={hallazgos} nombres={nombres} seleccionada={pieza} alSeleccionar={setPieza} />
      {pieza !== null && (
        <PiezaDetalle
          key={pieza}
          pieza={pieza}
          hallazgos={hallazgos}
          catalogo={catalogo}
          nombres={nombres}
          rol={rol}
          alRegistrar={async (datos: DatosHallazgo): Promise<void> => {
            await registrarHallazgo(historia.id, datos);
            await recargar(historia);
          }}
          alCorregir={async (id: number, datos: DatosHallazgo, motivo: string): Promise<void> => {
            await corregirHallazgo(historia.id, id, datos, motivo);
            await recargar(historia);
          }}
          alBaja={async (id: number, motivo: string): Promise<void> => {
            await darDeBajaHallazgo(historia.id, id, motivo);
            await recargar(historia);
          }}
          alCerrar={(): void => setPieza(null)}
        />
      )}
      <Suspense fallback={<p className="muted">Cargando presupuestos…</p>}>
        <PresupuestosPanel pacienteId={pacienteId} hallazgos={hallazgos} nombres={nombres} rol={rol} />
      </Suspense>
    </section>
  );
}
