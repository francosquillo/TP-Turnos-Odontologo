# Tasks: C-14 Dark Mode Theme Toggle

## 1. Tokens CSS Oscuros

- [x] 1.1 Definir variables de color para modo oscuro en `design-system/tokens.css` bajo el selector `[data-theme="dark"]` y verificar contraste visual.

## 2. Lógica de Tema y Control en Header

- [x] 2.1 Crear hook/utilidad `frontend/src/shared/theme/useTheme.ts` con soporte para `'light' | 'dark'`, inicialización con `prefers-color-scheme` y persistencia en `localStorage`.
- [x] 2.2 Integrar botón toggle con icono ☀️/🌙 en `frontend/src/shared/layout/AppHeader.tsx` con `aria-label` dinámico.

## 3. Pruebas y Verificación

- [x] 3.1 Agregar test unitario para alternancia y persistencia en `frontend/src/shared/theme/useTheme.test.ts` y verificar que pase en Vitest.
- [x] 3.2 Ejecutar suite completa de frontend (`npm test` y `tsc --noEmit`) asegurando 0 regresiones.
