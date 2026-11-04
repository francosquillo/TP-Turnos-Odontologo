# Proposal: C-14 Dark Mode Theme Toggle

## Why
El personal del consultorio y los pacientes utilizan el sistema en diferentes condiciones de iluminación (pantallas de recepción, consultorios con luz atenuada o uso nocturno). Contar con un modo oscuro alternable reduce la fatiga visual, mejora el confort y la accesibilidad, aprovechando que la arquitectura de diseño del Change 13 ya centralizó todos los estilos en variables semánticas de `tokens.css`.

## What Changes
- Definición de tokens de color oscuros en `design-system/tokens.css` bajo el selector `[data-theme="dark"]` (redefiniendo fondos, superficies, bordes y textos sin alterar la semántica ni los contrastes WCAG AA).
- Soporte para detección automática de preferencia de sistema operativo (`prefers-color-scheme: dark`).
- Módulo liviano de gestión de tema en `frontend/src/shared/theme/` con persistencia en `localStorage` (claves `'light'` | `'dark'`).
- Botón accesible de alternancia (toggle ☀️/🌙) en el `AppHeader` con `aria-label` descriptivo.
- Preservación del 100 % de los tests existentes y compatibilidad total con todas las 12 vistas del sistema.

## Capabilities

### New Capabilities
- `theme-mode-toggle`: Soporte de alternancia de tema claro/oscuro, persistencia local y sincronización con tokens semánticos del sistema de diseño.

### Modified Capabilities
Ninguna modificación a las capacidades funcionales previas.

## Impact
- **Archivos afectados**: `design-system/tokens.css`, `frontend/src/shared/layout/AppHeader.tsx`, nuevo `frontend/src/shared/theme/useTheme.ts`, tests de interfaz.
- **Backend / API**: Cero impacto.
- **Base de datos**: Cero impacto.
