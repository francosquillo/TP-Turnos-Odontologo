# Design: C-14 Dark Mode Theme Toggle

## Context
See `proposal.md` for problem statement and motivation. El sistema actual ya utiliza tokens CSS centralizados en `design-system/tokens.css` y consumidos en `layout.css` y `components.css`. Los componentes no tienen colores fijos incrustados.

## Goals / Non-Goals

**Goals:**
- Proporcionar un selector `[data-theme="dark"]` en `tokens.css` con variables de fondo y contraste WCAG AA.
- Crear un hook / utilidad reutilizable en TypeScript (`useTheme.ts`) que gestione el estado `'light' | 'dark'`, detecte `prefers-color-scheme` y persista en `localStorage`.
- Integrar un botón toggle accesible con icono sol/luna (☀️ / 🌙) en `AppHeader.tsx`.
- Mantener 100 % de los tests de Vitest pasando sin introducir nuevas dependencias pesadas ni bibliotecas externas.

**Non-Goals:**
- No se introducen temas personalizados arbitrarios adicionales (solo Claro y Oscuro).
- No se modifica ninguna API de backend ni esquema de base de datos.
- No se rediseñan las estructuras ni layouts de componentes existentes.

## UI Mockups
- Decision: no (project policy)

## Decisions

### D-01: Atributo `data-theme` en elemento raíz `<html>`
- **Elección**: Manipular el atributo `data-theme="dark"` (o `'light'`) directamente en `document.documentElement`.
- **Razón**: Permite que las variables CSS cascaden limpiamente a todos los subárboles (incluidos portales y modales) con especificidad mínima y sin overhead de renderizado en React.
- **Alternativas**: Clases `.dark` en `<body>` (más propensas a colisiones y especificidad desordenada).

### D-02: Detección y persistencia de preferencia
- **Elección**: Al inicializar, verificar `localStorage.getItem("theme")`. Si es nulo, consultar `window.matchMedia("(prefers-color-scheme: dark)").matches`. Guardar en `localStorage` ante cada alternancia.
- **Razón**: Respeta la preferencia nativa del usuario y preserva su elección manual entre recargas.

### D-03: Mapeo de tokens oscuros
- **Elección**:
  - `--color-bg`: `#0b0f19` (fondo principal profundo)
  - `--color-surface`: `#111827` (superficie de tarjetas y modales)
  - `--color-surface-subtle`: `#1f2937` (fondos de inputs, hover y tablas)
  - `--color-border`: `#374151` (bordes contrastados)
  - `--color-text`: `#f8fafc` (texto principal de alto contraste)
  - `--color-text-muted`: `#94a3b8` (texto secundario)
- **Razón**: Cumple con ratio de contraste WCAG AA >= 4.5:1 para texto normal y >= 3:1 para elementos de interfaz.

## Risks / Trade-offs

- [Risk] Posible parpadeo (FOUC) al recargar página si el tema guardado es oscuro → Mitigación: Inicializar `data-theme` antes del render de React o en script de arranque temprano en `index.html`.
- [Risk] Legibilidad de badges de estado semánticos en modo oscuro → Mitigación: Mantener los colores semánticos con opacidad o bordes visibles según `tokens.css`.
