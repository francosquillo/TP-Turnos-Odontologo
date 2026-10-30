# Sistema de diseño — Turnos Odontólogo

- Mode: system-only
- Revision: 1
- Approval: approved (2026-10-28, by user)
- Decisión de política: elegida por el usuario el 2026-10-27 (sistema aprobado antes de la UI, sin mockups por change). No volver a preguntar.

## Propósito

Fundación visual única para la SPA (React + TS + Vite). Se usa a partir de C-07 tarea 7.1 (cola de lista de espera del staff y página pública de oferta). Hasta ahora el frontend no tiene estilos: este sistema define la base, sin rebrand de nada establecido.

## Auditoría de la identidad existente (fuentes)

| Hallazgo | Fuente |
|---|---|
| No existe ningún archivo CSS, ni estilos globales, ni librería de UI, ni logo, ni imágenes. Todo es HTML semántico sin estilar. | `frontend/src` (sin `*.css`), `frontend/package.json` (solo react/react-dom) |
| Nombre provisional del producto: "Turnos Odontólogo". | `frontend/index.html` (`<title>`), `knowledge-base/README.md` |
| Único dato visual establecido: colores por estado de turno (`pendiente #b45309`, `confirmado #1d4ed8`, `asistido #15803d`, `ausente #6b7280`, `cancelado #b91c1c`), aplicados como borde izquierdo de 6 px en la card. Se conservan tal cual. | `frontend/src/features/agenda/tipos.ts` (`COLOR_POR_ESTADO`), `TurnoCard.tsx` |
| Estados de turno y de lista de espera (`activa / ofrecida / convertida / vencida`). | `tipos.ts`, `knowledge-base/04_modelo_de_datos.md` |
| Patrones de UI existentes: card de turno, modal de cancelación (`role="dialog"`), formulario de login, botones de píldoras de horario con `aria-pressed`, alertas `role="alert"`. | `TurnoCard.tsx`, `CancelarModal.tsx`, `Login.tsx`, `Reservas.tsx` |
| Tono: voseo rioplatense, directo ("Reservá tu turno", "Confirmá tu asistencia", "Llamá al consultorio"). Idioma `es`. | `Inicio.tsx`, `Confirmar.tsx`, `Reservas.tsx` |
| Público: paciente (móvil, sin cuenta) + staff (admin/odontólogo/secretaria, escritorio). Web responsiva, sin app nativa. | `knowledge-base/01_vision_y_objetivos.md`, `03_actores_y_roles.md` |

## Qué se propuso (no existía)

- Marca: verde azulado `#0f766e` (salud, distinto del azul de "confirmado" y de los colores de estado).
- Neutros slate, tipografía de sistema (sin fuentes remotas), escala de espaciado base 4 px, radios 4/8/12 px, sombras suaves, foco azul de 3 px, motion de 120-320 ms con `prefers-reduced-motion`.
- Colores de lista de espera: activa `#0e7490` (cian), ofrecida `#6d28d9` (violeta), convertida `#15803d` (verde), vencida `#475569` (slate). Cada badge lleva texto y punto, nunca solo color.
- Accesibilidad: contraste AA verificado por cálculo (texto 4.5:1 o más; badges 6.4:1 o más), objetivo táctil de 44 px, foco visible global, estados con texto.

## Archivos

- `tokens.css`: único lugar de valores visuales.
- `brand.js`: constante del nombre + binding de `[data-brand-name]`.
- `brand.md`: reglas de marca, tono, logo e imágenes.
- `components.html`: referencia de componentes y estados (importa `tokens.css` y `brand.js`).
- `assets/logo.svg`: logo PROVISIONAL.
- `previews/components-mobile.png` (390x844) y `previews/components-desktop.png` (1440x900).

## Decisiones abiertas (TBD)

1. (TBD) Nombre definitivo del producto (hoy "Turnos Odontólogo", tomado del `<title>`).
2. (TBD) Logo definitivo (hoy `assets/logo.svg` con la etiqueta visible "PROVISIONAL").
3. (TBD) Paleta de marca definitiva: el verde azulado es una propuesta; solo los colores de estado de turno están establecidos.
4. (TBD) Imágenes e ilustraciones (ninguna definida).
5. (TBD) Modo oscuro: fuera de v1 (`color-scheme: light`).
6. (TBD) Fuente de marca: se usa el stack del sistema; cambiar solo si se define una local.

## Cómo reemplazar

- Nombre: editar `BRAND_NAME` en `design-system/brand.js`. En la app, usar `<span data-brand-name>` o importar la constante; actualizar también `frontend/index.html` `<title>` y el texto del logo.
- Logo: reemplazar `design-system/assets/logo.svg` conservando la ruta y el nombre del archivo; quitar la etiqueta "PROVISIONAL" y el borde punteado.
- Colores, tipografía, espaciado, radios, sombras, foco y motion: editar solo `design-system/tokens.css`. Si cambia un token compartido, subir `Revision:` y volver a `Approval: pending`.
- Integración en la app (7.1): importar `tokens.css` desde el frontend (copiar o referenciar) y reemplazar `COLOR_POR_ESTADO` por variables `--estado-*`. Fuera del alcance de esta revisión.

## Aprobación

Aprobado por el usuario el 2026-10-28 (Revision 1, con nombre, logo y paleta de marca aún `(TBD)` y visiblemente provisionales). Si cambia un token o asset compartido, subir `Revision:` y volver a `Approval: pending` hasta una nueva aprobación.

Vista previa: abrir `design-system/components.html` en el navegador (doble clic, o `python -m http.server` desde esta carpeta si `file://` está bloqueado).
