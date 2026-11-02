import { ExportacionTotal } from "./ExportacionTotal";
import { ImportarPacientes } from "./ImportarPacientes";
import { UsuariosPage } from "./UsuariosPage";

/** Panel de administracion (solo admin): usuarios, importacion de pacientes y exportacion total. */
export function PanelAdmin(): JSX.Element {
  return (
    <>
      <UsuariosPage />
      <ImportarPacientes />
      <ExportacionTotal />
    </>
  );
}
