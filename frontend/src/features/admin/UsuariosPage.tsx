import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../../shared/api-client";
import { cambiarRol, crearUsuario, desactivarUsuario, listarUsuarios, reactivarUsuario } from "./api";
import { ETIQUETA_ROL, PASSWORD_MIN, ROLES, esRol } from "./tipos";
import type { Rol, UsuarioAdmin } from "./tipos";

type Carga =
  | { tipo: "cargando" }
  | { tipo: "error"; mensaje: string }
  | { tipo: "lista"; usuarios: UsuarioAdmin[] };

const mensajeDe = (fallo: unknown, porDefecto: string): string => {
  if (fallo instanceof ApiError) return fallo.httpStatus === 0 ? "No hay conexión con el servidor." : fallo.message;
  return porDefecto;
};

interface AltaFormProps {
  alCreado: (usuario: UsuarioAdmin) => void;
}

function AltaForm({ alCreado }: AltaFormProps): JSX.Element {
  const [nombre, setNombre] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [rol, setRol] = useState<Rol>("secretaria");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  async function enviar(e: FormEvent): Promise<void> {
    e.preventDefault();
    if (enviando) return;
    if (nombre.trim() === "" || email.trim() === "") {
      setError("Completá el nombre y el correo electrónico.");
      return;
    }
    if (password.length < PASSWORD_MIN) {
      setError(`La contraseña inicial necesita al menos ${PASSWORD_MIN} caracteres.`);
      return;
    }
    setError(null);
    setEnviando(true);
    try {
      const creado = await crearUsuario({ nombre: nombre.trim(), email: email.trim(), password, rol });
      setNombre("");
      setEmail("");
      setPassword("");
      setRol("secretaria");
      alCreado(creado);
    } catch (fallo) {
      setError(mensajeDe(fallo, "No se pudo crear el usuario."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form
      className="admin-alta card"
      aria-label="Nuevo usuario"
      noValidate
      onSubmit={(e): void => {
        void enviar(e);
      }}
    >
      <h3>Nuevo usuario</h3>
      <label className="field">
        Nombre
        <input className="input" type="text" value={nombre} maxLength={120} onChange={(e): void => setNombre(e.target.value)} />
      </label>
      <label className="field">
        Correo electrónico
        <input className="input" type="email" value={email} maxLength={320} onChange={(e): void => setEmail(e.target.value)} />
      </label>
      <label className="field">
        Contraseña inicial
        <input
          className="input"
          type="password"
          value={password}
          autoComplete="new-password"
          onChange={(e): void => setPassword(e.target.value)}
        />
      </label>
      <label className="field">
        Rol
        <select
          className="input"
          value={rol}
          onChange={(e): void => {
            if (esRol(e.target.value)) setRol(e.target.value);
          }}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ETIQUETA_ROL[r]}
            </option>
          ))}
        </select>
      </label>
      {error !== null && (
        <p role="alert" className="banner banner-error">
          {error}
        </p>
      )}
      <button type="submit" className="btn btn-primary" disabled={enviando}>
        Crear usuario
      </button>
    </form>
  );
}

interface FilaProps {
  usuario: UsuarioAdmin;
  ocupado: boolean;
  alCambiarRol: (usuario: UsuarioAdmin, rol: Rol) => void;
  alAlternarActivo: (usuario: UsuarioAdmin) => void;
}

function Fila({ usuario, ocupado, alCambiarRol, alAlternarActivo }: FilaProps): JSX.Element {
  return (
    <tr data-activo={usuario.activo}>
      <td>{usuario.nombre}</td>
      <td>{usuario.email}</td>
      <td>
        <select
          className="input input-compact"
          aria-label={`Rol de ${usuario.nombre}`}
          value={usuario.rol}
          disabled={ocupado}
          onChange={(e): void => {
            if (esRol(e.target.value)) alCambiarRol(usuario, e.target.value);
          }}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ETIQUETA_ROL[r]}
            </option>
          ))}
        </select>
      </td>
      <td>
        <span className="badge" data-estado={usuario.activo ? "confirmado" : "cancelado"}>
          {usuario.activo ? "Activo" : "Inactivo"}
        </span>
      </td>
      <td>
        <button
          type="button"
          className={`btn btn-sm ${usuario.activo ? "btn-secondary" : "btn-primary"}`}
          disabled={ocupado} onClick={(): void => alAlternarActivo(usuario)}>
          {usuario.activo ? "Desactivar" : "Reactivar"}
        </button>
      </td>
    </tr>
  );
}

/** Gestión de usuarios (solo admin): lista, alta, cambio de rol, desactivar y reactivar.
 * No ofrece eliminar: un usuario con historial solo se desactiva (RN-GL-01). */
export function UsuariosPage(): JSX.Element {
  const [carga, setCarga] = useState<Carga>({ tipo: "cargando" });
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupadoId, setOcupadoId] = useState<number | null>(null);

  const cargar = useCallback(async (): Promise<void> => {
    try {
      setCarga({ tipo: "lista", usuarios: await listarUsuarios() });
    } catch (fallo) {
      setCarga({ tipo: "error", mensaje: mensajeDe(fallo, "No se pudo cargar los usuarios.") });
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function aplicar(usuario: UsuarioAdmin, accion: () => Promise<UsuarioAdmin>): Promise<void> {
    setAviso(null);
    setOcupadoId(usuario.id);
    try {
      const nuevo = await accion();
      setCarga((previo) =>
        previo.tipo === "lista"
          ? { tipo: "lista", usuarios: previo.usuarios.map((u) => (u.id === nuevo.id ? nuevo : u)) }
          : previo,
      );
    } catch (fallo) {
      // La lista queda como estaba: el motivo del backend (por ejemplo, ultimo admin) se muestra tal cual.
      setAviso(mensajeDe(fallo, "No se pudo completar la acción."));
    } finally {
      setOcupadoId(null);
    }
  }

  if (carga.tipo === "cargando") return <p>Cargando usuarios…</p>;
  if (carga.tipo === "error") {
    return (
      <p role="alert" className="banner banner-error">
        {carga.mensaje}
      </p>
    );
  }

  return (
    <section className="admin-usuarios" aria-label="Usuarios">
      <h2>Usuarios</h2>
      {aviso !== null && (
        <p role="alert" className="banner banner-error">
          {aviso}
        </p>
      )}
      <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Nombre</th>
            <th scope="col">Correo</th>
            <th scope="col">Rol</th>
            <th scope="col">Estado</th>
            <th scope="col">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {carga.usuarios.map((usuario) => (
            <Fila
              key={usuario.id}
              usuario={usuario}
              ocupado={ocupadoId === usuario.id}
              alCambiarRol={(u, rol): void => {
                void aplicar(u, () => cambiarRol(u.id, rol));
              }}
              alAlternarActivo={(u): void => {
                void aplicar(u, () => (u.activo ? desactivarUsuario(u.id) : reactivarUsuario(u.id)));
              }}
            />
          ))}
        </tbody>
      </table>
      </div>
      <AltaForm
        alCreado={(usuario): void => {
          setAviso(null);
          setCarga((previo) =>
            previo.tipo === "lista" ? { tipo: "lista", usuarios: [...previo.usuarios, usuario] } : previo,
          );
        }}
      />
    </section>
  );
}
