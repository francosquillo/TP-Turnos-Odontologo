/** Entrega un `Blob` al usuario como descarga (enlace temporal con URL de objeto). */
export function guardarArchivo(blob: Blob, nombre: string): void {
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  document.body.removeChild(enlace);
  URL.revokeObjectURL(url);
}

export type GuardarArchivo = (blob: Blob, nombre: string) => void;
