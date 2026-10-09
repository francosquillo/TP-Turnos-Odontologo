import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError } from "../shared/api-client";
import { useAuth } from "../shared/auth-context";

/** Login C-03: 401 generico -> "credenciales inválidas" (sin enumerar). */
export function Login(): JSX.Element {
  const { iniciarSesion } = useAuth();
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<boolean>(false);

  async function alEnviar(evento: FormEvent): Promise<void> {
    evento.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await iniciarSesion(email, password);
    } catch (fallo) {
      if (fallo instanceof ApiError && fallo.httpStatus === 401) {
        setError("credenciales inválidas");
      } else {
        setError("No se pudo iniciar sesión, intentá de nuevo.");
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={(e): Promise<void> => alEnviar(e)}>
      <label htmlFor="login-email">Email</label>
      <input
        id="login-email"
        type="email"
        value={email}
        onChange={(e): void => setEmail(e.target.value)}
        required
      />
      <label htmlFor="login-password">Contraseña</label>
      <input
        id="login-password"
        type="password"
        value={password}
        onChange={(e): void => setPassword(e.target.value)}
        required
      />
      <button type="submit" disabled={enviando}>
        Ingresar
      </button>
      {error !== null && <p role="alert">{error}</p>}
    </form>
  );
}
