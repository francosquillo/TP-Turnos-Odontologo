interface Props {
  /** `null` = no relevadas (nunca se interpreta como "sin alergias"). */
  alergias: string | null;
}

/** Aviso permanente: lleva etiqueta de texto, el color no es el unico portador del dato. */
export function AlergiasAviso({ alergias }: Props): JSX.Element {
  return (
    <aside role="note" aria-label="Aviso de alergias" className="banner banner-warning odonto-alergias">
      <span className="banner-texto">
        {alergias === null ? (
          <strong>Alergias no relevadas: preguntar al paciente antes de indicar medicación.</strong>
        ) : (
          <>
            <strong>Alergias:</strong> {alergias}
          </>
        )}
      </span>
    </aside>
  );
}
