# Marca — Turnos Odontólogo

Revision 1 · Approval: pending

## Nombre

- "Turnos Odontólogo". Fuente: `frontend/index.html` (`<title>`). (TBD) nombre definitivo.
- Se escribe en un solo lugar: `design-system/brand.js`. Evitar copiarlo a mano en pantallas.

## Logo

- Hoy no existe logo real. `design-system/assets/logo.svg` es un placeholder con una muela estilizada y la etiqueta visible "PROVISIONAL". (TBD) logo definitivo.
- Ruta estable: `design-system/assets/logo.svg`. Reemplazar el archivo sin cambiar la ruta.
- Reglas: alto mínimo 32 px; espacio libre alrededor igual a la mitad del alto; sobre fondo claro; no deformar ni recolorear fuera de los tokens.

## Imágenes

- Ninguna definida (TBD). Mientras tanto: sin fotos de stock de pacientes ni de personas reales. Datos 100% ficticios (ver `knowledge-base/` y regla del proyecto sobre datos reales).
- Si se agregan ilustraciones: estilo simple, línea o formas planas con los colores de `tokens.css`, `alt` descriptivo.

## Tono

- Español rioplatense, voseo, directo y cálido. Fuente: `Inicio.tsx`, `Confirmar.tsx`, `Reservas.tsx`.
- Sentence case en títulos, botones y etiquetas: "Reservar turno", no "Reservar Turno".
- Verbos en imperativo voseado: "Reservá", "Confirmá", "Llamá al consultorio".
- Errores: decir qué pasó y qué hacer. Ejemplo: "El link venció. Llamá al consultorio para reprogramar."
- Nunca datos clínicos en mensajes por canales planos (regla RN-CL-04 / RN-NO-04).

## Color de marca

- Verde azulado `#0f766e` como primario (propuesta, TBD). Colores de estado de turno: conservados de `frontend/src/features/agenda/tipos.ts`.
