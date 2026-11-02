import { useEffect, useState } from "react";
import { ApiError } from "../../shared/api-client";
import { formatearMoneda } from "../../shared/moneda";
import { listarTratamientos } from "../presupuestos/api";
import type { Tratamiento } from "../presupuestos/tipos";
import { asignarPlanPaciente, listarPlanes, obtenerPlanPaciente, validarCobertura } from "./cobertura-api";
import type { PlanDelCatalogo, PlanPaciente, ValidadorCobertura } from "./cobertura-tipos";

interface Props {
  pacienteId: number;
}

type Carga =
  | { tipo: "cargando" }
  | { tipo: "error" }
  | { tipo: "lista"; plan: PlanPaciente; planes: PlanDelCatalogo[]; tratamientos: Tratamiento[] };

const mensajeDe = (fallo: unknown, porDefecto: string): string =>
  fallo instanceof ApiError ? fallo.message : porDefecto;

function textoPlan(plan: PlanPaciente): string {
  return plan.plan_nombre === null
    ? "Plan actual: Sin plan de obra social"
    : `Plan actual: ${plan.plan_nombre} (${plan.obra_social_nombre ?? "—"})`;
}

function Resultado({ v }: { v: ValidadorCobertura }): JSX.Element {
  return (
    <div className="cobertura-resultado" aria-label="Resultado de la cobertura" aria-live="polite" data-estado={v.estado}>
      {v.estado === "cubierto" && (
        <>
          <p className="cobertura-estado">Cubierto por la obra social</p>
          <p>
            Precio del tratamiento: <strong>{formatearMoneda(v.precio)}</strong>
          </p>
          <p>
            Cubierto: <strong>{formatearMoneda(v.cubierto)}</strong> ({v.porcentaje} %)
          </p>
          <p>
            A cargo del paciente: <strong>{formatearMoneda(v.a_cargo)}</strong>
          </p>
        </>
      )}
      {v.estado === "sin_arancel" && (
        <>
          <p className="cobertura-estado">Sin arancel vigente para este tratamiento</p>
          <p>
            Todo el precio queda a cargo del paciente: <strong>{formatearMoneda(v.a_cargo)}</strong>
          </p>
        </>
      )}
      {v.estado === "sin_plan" && (
        <>
          <p className="cobertura-estado">El paciente no tiene un plan activo</p>
          <p>
            Todo el precio queda a cargo del paciente: <strong>{formatearMoneda(v.a_cargo)}</strong>
          </p>
        </>
      )}
    </div>
  );
}

/** Plan de obra social del paciente y validador de cobertura (C-11). Los importes y el porcentaje
 * vienen del servidor. Sus avisos NO usan los roles `alert` ni `status`: la cuenta ya tiene los
 * suyos y una falla de la cobertura no debe tapar el saldo. */
export function PanelCobertura({ pacienteId }: Props): JSX.Element {
  const [carga, setCarga] = useState<Carga>({ tipo: "cargando" });
  const [planElegido, setPlanElegido] = useState<string>("");
  const [tratamientoElegido, setTratamientoElegido] = useState<string>("");
  const [validador, setValidador] = useState<ValidadorCobertura | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<boolean>(false);

  useEffect(() => {
    let vigente = true;
    setCarga({ tipo: "cargando" });
    setValidador(null);
    setAviso(null);
    Promise.all([obtenerPlanPaciente(pacienteId), listarPlanes(), listarTratamientos()])
      .then(([plan, planes, tratamientos]) => {
        if (!vigente) return;
        setPlanElegido(plan.plan_id === null ? "" : String(plan.plan_id));
        setCarga({ tipo: "lista", plan, planes, tratamientos });
      })
      .catch(() => {
        if (vigente) setCarga({ tipo: "error" });
      });
    return (): void => {
      vigente = false;
    };
  }, [pacienteId]);

  if (carga.tipo === "cargando") {
    return (
      <section className="cobertura" aria-label="Cobertura de obra social">
        <p className="muted">Cargando cobertura…</p>
      </section>
    );
  }

  if (carga.tipo === "error") {
    return (
      <section className="cobertura" aria-label="Cobertura de obra social">
        <p className="banner banner-warning">No se pudo cargar la cobertura de obra social.</p>
      </section>
    );
  }

  const { plan, planes, tratamientos } = carga;

  async function guardarPlan(): Promise<void> {
    if (ocupado) return;
    setAviso(null);
    setOcupado(true);
    try {
      const nuevo = await asignarPlanPaciente(pacienteId, planElegido === "" ? null : Number(planElegido));
      setCarga({ tipo: "lista", plan: nuevo, planes, tratamientos });
      setValidador(null);
      setTratamientoElegido("");
    } catch (fallo) {
      setAviso(mensajeDe(fallo, "No se pudo guardar el plan"));
    } finally {
      setOcupado(false);
    }
  }

  async function consultar(valor: string): Promise<void> {
    setTratamientoElegido(valor);
    setValidador(null);
    setAviso(null);
    if (valor === "") return;
    try {
      setValidador(await validarCobertura(pacienteId, Number(valor)));
    } catch (fallo) {
      setAviso(mensajeDe(fallo, "No se pudo consultar la cobertura"));
    }
  }

  return (
    <section className="cobertura" aria-label="Cobertura de obra social">
      <h3>Cobertura de obra social</h3>
      <p className="cobertura-plan">{textoPlan(plan)}</p>

      <div className="cobertura-campos">
        <div className="field">
          <label htmlFor="cobertura-plan">Plan del paciente</label>
          <select
            id="cobertura-plan"
            className="input"
            value={planElegido}
            onChange={(e): void => setPlanElegido(e.target.value)}
          >
            <option value="">Sin plan</option>
            {planes
              .filter((p) => p.activo)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.obra_social_nombre} · {p.nombre}
                </option>
              ))}
          </select>
        </div>
        <button type="button" className="btn btn-secondary btn-sm" disabled={ocupado} onClick={(): void => void guardarPlan()}>
          Guardar plan
        </button>
      </div>

      <div className="field">
        <label htmlFor="cobertura-tratamiento">Tratamiento</label>
        <select
          id="cobertura-tratamiento"
          className="input"
          value={tratamientoElegido}
          onChange={(e): void => void consultar(e.target.value)}
        >
          <option value="">Elegí un tratamiento para ver la cobertura</option>
          {tratamientos.map((t) => (
            <option key={t.id} value={t.id}>
              {t.nombre}
            </option>
          ))}
        </select>
      </div>

      {aviso !== null && <p className="banner banner-error">{aviso}</p>}
      {validador !== null && <Resultado v={validador} />}
    </section>
  );
}
