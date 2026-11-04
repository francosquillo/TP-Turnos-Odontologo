---
name: dental-ui-polish
description: >
  Reglas de ingeniería de diseño y UI polish para el sistema odontológico.
  Usa tokens.css, accesibilidad WCAG AA, feedback táctil y preserva tests.
---

# dental-ui-polish

Guía técnica de estilización y refactor visual para el frontend odontológico.

## 1. Fuentes de verdad y tokens

- Todos los valores visuales provienen de `frontend/src/styles/tokens.css` (o `design-system/tokens.css`).
- Marca principal: `--color-primary` (`#0f766e`), hover `--color-primary-hover` (`#115e59`), suave `--color-primary-soft` (`#ccfbf1`).
- Neutros: fondo `--color-bg` (`#f8fafc`), superficie `--color-surface` (`#ffffff`), texto `--color-text` (`#0f172a`), bordes `--color-border` (`#cbd5e1`).
- Estados de turno: usar variables `--estado-pendiente`, `--estado-confirmado`, `--estado-asistido`, `--estado-ausente`, `--estado-cancelado` (con sus variantes `-bg` y `-text`).
- Prohibido hardcodear colores hex, rgb o nombres CSS en componentes salvo referencia a variables CSS.

## 2. Componentes base y clases estándar

Referencia canónica: `design-system/components.html`.

- Contenedor de página: `.wrap` (máximo ancho `1200px`, padding responsive).
- Botones: `.btn` con modificador `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-ghost`, `.btn-sm`.
- Campos de formulario: `.field` conteniendo `<label>`, `.input` (o `textarea.input`), `.hint` y `.error-msg`.
- Tarjetas: `.card` con padding `var(--space-4)` y borde `1px solid var(--color-border)`.
- Tablas: `.table-wrap` con `table` responsive, headers alineados y filas alternadas discretas.

## 3. Microinteracciones y accesibilidad (Emil Kowalski + WCAG AA)

- Feedback táctil en botones: `.btn:active:not(:disabled) { transform: scale(0.97); }`.
- Transición en botones e inputs: `var(--motion-fast) var(--ease-out)` (120ms). Prohibido `transition: all`.
- Foco por teclado visible: `outline: var(--focus-ring); outline-offset: var(--focus-offset);`.
- Respeto de accesibilidad: `@media (prefers-reduced-motion: reduce) { * { transition-duration: 0.01ms !important; } }`.
- Contraste mínimo: 4.5:1 en texto normal sobre fondo, 3:1 en bordes de control e inputs.

## 4. Densidad y roles

- **Vistas públicas (Paciente / Móvil 390x844)**: `Inicio`, `Reservas`, `Confirmar`, `OfertaEspera`, `Seguridad`. Baja densidad, objetivos táctiles >= 44px (`--target-min`), textos claros en voseo rioplatense.
- **Vistas staff (Secretaría / Profesional / Admin / Desktop 1440x900)**: `Agenda`, `Odontograma`, `Cuenta`, `Caja`, `Liquidaciones`, `Admin`. Alta densidad de datos, tablas compactas, métricas clave visibles sin scroll excesivo.

## 5. Regla dura: Preservación de tests de Vitest

- NUNCA remover ni modificar `data-testid`, `role`, atributos `id`, `htmlFor` ni textos evaluados en assertions de Vitest.
- NUNCA alterar firmas de props de componentes (`alConfirmar`, `alAbrir`, `alVolver`, etc.).
- Toda modificación debe dejar los 421 tests pasando (`npm test`) y compilar limpia (`tsc --noEmit`).

## 6. Formato de revisión obligatorio

Documentar cada cambio visual en tabla:

| Componente | Antes | Después | Motivo (Why) |
|---|---|---|---|
