import { useState } from "react";
import { ApiError } from "../../shared/api-client";
import { guardarArchivo } from "../liquidaciones/descarga";
import type { GuardarArchivo } from "../liquidaciones/descarga";
import { descargarExportacionTotal } from "./api";

interface Props {
  /** Entrega el archivo al usuario; se inyecta en los tests. */
  guardar?: GuardarArchivo;
}

/** Descarga de todos los datos del consultorio en un ZIP de CSV (solo admin, RN-GL-01). */
export function ExportacionTotal({ guardar = guardarArchivo }: Props): JSX.Element {
  const [descargando, setDescargando] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  async function descargar(): Promise<void> {
    if (descargando) return;
    setError(null);
    setDescargando(true);
    try {
      const { blob, nombre } = await descargarExportacionTotal();
      guardar(blob, nombre);
    } catch (fallo) {
      setError(fallo instanceof ApiError ? fallo.message : "No se pudo descargar la exportación.");
    } finally {
      setDescargando(false);
    }
  }

  return (
    <section className="admin-exportacion" aria-label="Exportación total">
      <h2>Exportación total</h2>
      <p>
        Descargá todos los datos del consultorio en un ZIP con un archivo CSV por tabla. Incluye
        datos clínicos: guardalo en un lugar seguro. No incluye contraseñas.
      </p>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      <button
        type="button"
        disabled={descargando}
        onClick={(): void => {
          void descargar();
        }}
      >
        Descargar exportación total
      </button>
    </section>
  );
}
