import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const THEME_STORAGE_KEY = "theme";

function detectarTemaInicial(): Theme {
  const guardado = localStorage.getItem(THEME_STORAGE_KEY);
  if (guardado === "light" || guardado === "dark") {
    return guardado;
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

function aplicarTemaAlDocumento(tema: Theme): void {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", tema);
  }
}

export interface UseThemeRetorno {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (tema: Theme) => void;
}

export function useTheme(): UseThemeRetorno {
  const [theme, setTemaState] = useState<Theme>(detectarTemaInicial);

  useEffect(() => {
    aplicarTemaAlDocumento(theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const toggleTheme = (): void => {
    setTemaState((previo) => (previo === "light" ? "dark" : "light"));
  };

  const setTheme = (nuevoTema: Theme): void => {
    setTemaState(nuevoTema);
  };

  return { theme, toggleTheme, setTheme };
}
