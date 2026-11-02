import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { importarPacientes } from "./api";
import type { ReporteImportacion } from "./api";

const plural = (n: number, uno: string, varios: string): string => `${n} ${n === 1 ? uno : varios}`;

/** Importación de pacientes desde CSV o XLSX: muestra cuántos se crearon y qué filas se rechazaron. */
export function ImportarPacientes(): JSX.Element {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reporte, setReporte] = useState<ReporteImportacion | null>(null);

  function elegir(e: ChangeEvent<HTMLInputElement>): void {
    setArchivo(e.target.files?.[0] ?? null);
    setReporte(null);
    setError(null);
  }

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (archivo === null || enviando) return;
    setError(null);
    setReporte(null);
    setEnviando(true);
    try {
      setReporte(await importarPacientes(archivo));
    } catch (fallo) {
      setError(fallo instanceof ApiError ? fallo.message : "No se pudo importar el archivo.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="admin-importacion" aria-label="Importar pacientes">
      <h2>Importar pacientes</h2>
      <p>
        Subí un archivo CSV (UTF-8) o XLSX con las columnas nombre y apellido, y opcionalmente dni, telefono y
        email. Máximo 2000 filas y 1 MB. Las filas con errores se saltean y se informan abajo.
      </p>
      <form
        onSubmit={(e): void => {
          void enviar(e);
        }}
      >
        <label>
          Archivo CSV o XLSX
          <input type="file" accept=".csv,.xlsx" onChange={elegir} />
        </label>
        <button type="submit" disabled={archivo === null || enviando}>
          Importar pacientes
        </button>
      </form>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      {reporte !== null && (
        <div role="status">
          <p>
            {plural(reporte.creados, "paciente creado", "pacientes creados")} y{" "}
            {plural(reporte.rechazados, "fila rechazada", "filas rechazadas")}.
          </p>
          {reporte.errores.length > 0 && (
            <table aria-label="Filas rechazadas">
              <thead>
                <tr>
                  <th scope="col">Fila</th>
                  <th scope="col">Motivo</th>
                </tr>
              </thead>
              <tbody>
                {reporte.errores.map((e) => (
                  <tr key={e.fila}>
                    <td>{e.fila}</td>
                    <td>{e.motivo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
