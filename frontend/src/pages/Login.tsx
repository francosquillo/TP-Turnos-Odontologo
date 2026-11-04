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
    <div className="wrap-sm" style={{ marginTop: "var(--space-6)" }}>
      <section className="card" style={{ padding: "var(--space-6)" }}>
        <h1 style={{ color: "var(--color-primary)", marginBottom: "var(--space-2)", textAlign: "center" }}>
          Ingreso al sistema
        </h1>
        <p className="muted" style={{ textAlign: "center", marginBottom: "var(--space-5)" }}>
          Acceso exclusivo para personal odontológico y administrativo.
        </p>

        <form onSubmit={(e): Promise<void> => alEnviar(e)}>
          <div className="field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              className="input"
              type="email"
              placeholder="usuario@consultorio.com"
              value={email}
              onChange={(e): void => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="login-password">Contraseña</label>
            <input
              id="login-password"
              className="input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e): void => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", marginTop: "var(--space-2)" }}
            disabled={enviando}
          >
            {enviando ? "Ingresando..." : "Ingresar"}
          </button>

          {error !== null && (
            <div className="banner banner-error" style={{ marginTop: "var(--space-4)" }}>
              <p role="alert" style={{ margin: 0 }}>{error}</p>
            </div>
          )}
        </form>
      </section>
    </div>
  );
}
