# Design — c-05-reserva-online-publica

## Context

Ver `proposal.md` (Why). Estado actual: C-04 archivado (tabla `turno` con doble
EXCLUDE parcial, `token_confirmacion_hash` nullable siempre NULL, servicio
`agenda_servicio` con `calcular_huecos`/`crear_turno`/`cambiar_estado`/
`sugerir_alternativas`, routers staff con `require_role`, stubs frontend
`pages/Reservas.tsx` y `pages/Confirmar.tsx` con texto "llega en C-05").
Restricciones vinculantes: reutilizar `disponibilidad` de C-04 SIN cambios de
cálculo, máquina de estados intacta (`origen=online` nace `pendiente`),
RBAC existente (rutas públicas SIN `require_role`), Pydantic `extra='forbid'`,
`Annotated[..., Depends(...)]` para DB, `async def` solo si todo adentro es
async no bloqueante, TS estricto sin `any`, tests contra Postgres real (nunca
SQLite), `freezegun` para tiempos (token 72 h), TZ
`America/Argentina/Buenos_Aires`, sede única, datos 100% ficticios, sin
`DELETE` de negocio, sin PHI en respuestas públicas.

## Goals / Non-Goals

**Goals:**

- Paciente reserva 24/7 sin cuenta y confirma en 1 clic, con la agenda
  actualizada sin intervención de secretaría (Flujo 1 completo).
- Token imposible de reusar o predecir, con expiración probada y sin fugas de
  información (no enumerar turnos ajenos).
- Carrera online+secretaría por el mismo hueco degradada a `409` + re-oferta,
  nunca a doble reserva (la DB sigue decidiendo).
- Tasks listas para TDD estricto en apply (RED primero, verificación por task).

**Non-Goals:**

- Envío real de WhatsApp con el link (C-06; acá la pantalla de éxito dice
  "revisá tu WhatsApp" como texto y el token viaja en la respuesta de la API
  para la demo local).
- Lista de espera y cascada 2 h (C-07), validador OS pre-turno (C-11), Google
  Calendar (C-12), cancelación por token del paciente (solo confirmación en
  v1.0 del change; cancelar sigue siendo tarea de secretaría).
- Migración SQL (la columna hash ya existe) y cambios al cálculo de huecos o a
  la máquina de estados.
- Multi-sede, pagos, AFIP (fuera de v1.0 por reglas duras).

## Decisions

### D-01 — Token opaco 256 bits, solo hash SHA-256 en DB, un solo uso

El servidor genera `secrets.token_urlsafe(32)` (256 bits) y persiste
`sha256(token).hexdigest()` en `token_confirmacion_hash`; el plano NUNCA se
guarda ni se loguea. Confirmar (`GET /confirmar/:token`) hashea el token de la
URL y busca por el hash con el índice parcial ya creado en C-04. Al confirmar
con éxito el hash se pone en NULL (invalida el token: un solo uso, RN-TU-04);
cualquier uso posterior del mismo token → `410 Gone`. Token inexistente →
`404` (sin distinguir "nunca existió" de "ya usado" en el mensaje, para no
filtrar qué tokens fueron reales). Expirado (D-02) → `410` con cuerpo
`{"detail": "token expirado", "contacto": "<teléfono consultorio>"}`.
Alternativa (JWT firmado como token) descartada: el JWT no es revocable sin
lista de revocación y este flujo exige invalidación explícita al primer uso;
el hash opaco + NULL es revocación trivial con una columna ya existente.
Revisión humana: confirmar que `410` (no `404`) para reusado/expirado es la
semántica aceptada por la cátedra.
Skills: `fastapi`, `python-testing-patterns`.

### D-02 — Expiración = min(72 h desde creación, inicio del turno)

Al crear la reserva se persiste `token_expira_en = min(creado_en + 72 h,
inicio)`; hacen falta dos columnas nuevas? NO: `inicio` ya existe y el
`created_at` del turno es el momento de creación, así que la expiración se
deriva sin DDL (`expirado = ahora >= min(created_at + 72h, inicio)`).
`freezegun` en tests para los tres bordes (dentro de ventana, pasado 72 h,
pasado el inicio aunque no pasen 72 h). Un turno cuyo inicio ya pasó no es
confirmable (expirado → `410` + contacto). Alternativa (columna
`token_expira_en` explícita) descartada: duplica información derivable y
obligaría a la única migración del change, violando el objetivo "SQL cero".
Revisión humana: si la cátedra prefiere columna explícita por legibilidad,
agregarla en apply es una migración de 5 líneas sin cambiar specs.

### D-03 — `POST /reservas`: valida hueco, matchea/crea paciente mínimo, delega en `crear_turno`

Flujo del endpoint (público, sin auth): (1) valida esquema `ReservaIn`
(profesional_id, sillon_id, inicio, fin, nombre, teléfono — ver D-05);
(2) verifica que `[inicio, fin)` sea un hueco ofrecible AHORA con
`calcular_huecos` (mismo servicio C-04, con ocupados frescos de la DB);
si no lo es → `409 {"detail": "hueco ocupado", "alternativas": [...]}` con
`sugerir_alternativas`; (3) matchea o crea el paciente mínimo (D-05);
(4) llama `crear_turno(..., origen="online")` que nace `pendiente` y aplica el
pre-chequeo + EXCLUDE como autoridad final (carrera → `HuecoOcupadoError` →
`409` con re-oferta); (5) genera token (D-01), Guarda solo el hash + responde
`201 {"turno_id", "estado": "pendiente", "token", "expira_en"}`. Sin
`Sobre_turno` desde la vía pública: la reserva online NUNCA crea sobreturnos
(el flag solo existe en routers staff). `creado_por` queda NULL (sin JWT).
Skill: `fastapi` (esquemas estrictos, `extra='forbid'`).

### D-04 — Disponibilidad pública = mismo cálculo, sin auth, sin datos de pacientes

`GET /disponibilidad` gana variante pública que ejecuta EXACTAMENTE el mismo
`calcular_huecos` con los mismos filtros (`profesional_id, desde, hasta,
sillon_id, duracion_min`) y devuelve solo `[{inicio, fin}]` (sin IDs de
turnos, sin nombres, sin teléfonos: no enumera agenda ajena). La variante
staff con `require_role` sigue existiendo para la UI de secretaría. Exigir
`profesional_id` siempre (nunca "toda la agenda sin filtro") para no exponer
la ocupación completa del consultorio de un golpe. Rate-limit leve en ambas
variantes públicas si es trivial con el stack (p. ej. `slowapi` si ya es
dependencia, o dependencia casera por IP en memoria); si no es trivial, deuda
documentada para C-12. Alternativa (endpoint separado `/disponibilidad-publica`)
descartada: duplica ruta y documentación para idéntico cálculo; una rama sin
auth en el router existente es menos código y un solo contrato que testear.

### D-05 — Paciente mínimo: nombre + teléfono, match por teléfono normalizado

`ReservaIn` exige `nombre` (≥ 2 caracteres) y `telefono` (normalizado:
solo dígitos, mínimo 8); `dni`/`email` opcionales. Match: busca paciente por
teléfono normalizado no soft-deleted; si existe, reutiliza (no duplica); si no,
crea paciente mínimo (`nombre`, `telefono`, resto NULL) con soft-delete
disponible según RN-GL-01. Teléfono normalizado se guarda tal cual en la
columna existente (sin nueva columna). Sin validación de propiedad del número
en v1.0 (no hay SMS de verificación hasta C-06 mock/real): se documenta como
riesgo aceptado (abuso = turno pendiente que secretaría cancela; nunca mueve
dinero ni datos clínicos). Alternativa (DNI obligatorio) descartada:
US-002 CA-3 pide "paciente mínimo" y el DNI frena la conversión en la vía
pública; el teléfono es el identificador operativo (recordatorios C-06).

### D-06 — Confirmar actualiza la agenda vía la máquina existente, sin intervención

`GET /confirmar/:token` (público): hashea, busca turno con ese hash; si no hay
→ `404`; si expirado (D-02) → `410` + contacto; si el turno ya no está
`pendiente` (p. ej. secretaría lo canceló) → `410` con detalle honesto
("este turno ya fue cancelado, llamá al consultorio"); si `pendiente` →
`cambiar_estado(turno, "confirmado")` (transición ya permitida en C-04) +
invalida el hash (NULL) en la misma transacción → `200 {"estado":
"confirmado", "inicio", "fin", "profesional"}` (solo datos del propio turno,
RN-TU-03). Idempotencia ante doble clic: el segundo GET ve hash NULL →
`404`? NO: vería "no encontrado" tras haber confirmado. Para no confundir al
paciente que toca dos veces, el servicio recuerda la confirmación reciente?
Decisión: segundo uso → `410 {"detail": "este turno ya fue confirmado"}` solo
si el turno referenciado sigue identificable; como el hash se borra, el
servidor no puede mapear el token al turno. Compromiso: al confirmar, antes de
borrar, registra en log estructurado (sin PHI) `turno_id + hash_prefix(8)`;
ante token desconocido responde `404` genérico. El frontend evita el doble
submit deshabilitando el botón tras el primer `200`. Revisión humana: aceptar
que doble-clic tras éxito muestra `404` genérico (no `410` específico) salvo
que se añada tabla de tokens usados —fuera de scope v1.0—.

### D-07 — Frontend público: 3 pasos + pantallas de token + landing

`pages/Reservas.tsx` (reemplaza stub): paso 1 selector profesional (+ día) →
pide `GET /disponibilidad` pública; paso 2 grilla de huecos (slots del
servicio, respeta RN-TU-05 por construcción); paso 3 formulario mínimo
(nombre+teléfono) → `POST /reservas`; éxito muestra resumen + "te enviamos el
link por WhatsApp" (texto hasta C-06) y, en demo local, el link de
confirmación; `409` → panel de `alternativas` servidas por la API sin perder
los datos del formulario (mismo patrón rollback/re-oferta de C-04 D-06).
`pages/Confirmar.tsx` (reemplaza stub): lee `:token` de la URL, llama
`GET /confirmar/:token`, estados `cargando|confirmado|expirado|invalido`;
expirado/inválido muestran teléfono del consultorio (env `VITE_CONSULTORIO_TEL`
o constante documentada, dato ficticio). `GET /` landing pública con links a
`/reservas` y a `/seguridad` (C-12 la completa). Todo fuera del guard de
roles; `fetch` sin Bearer; tipado estricto sin `any`, componentes PascalCase.
Skill: `vercel-react-best-practices` (aplicar bundle/waterfall/rerender;
ignorar RSC/`next/dynamic` — proyecto Vite SPA).

### D-08 — Cero migración y cero cambios a staff: C-05 es aditivo

Sin archivos de migración (columna hash + índice parcial ya existen; expiración
derivada de `created_at`+`inicio`, D-02). `agenda_servicio.py`,
`disponibilidad` staff, `turnos.py`, máquina de estados y EXCLUDE intactos; el
nuevo `reserva_servicio.py` compone (no copia) las funciones C-04. `TurnoOut`
staff no expone el hash (sigue opaco/ausente como en C-04); `ReservaOut` es el
único esquema que lleva el token plano, y solo en la respuesta `201` de
creación. Rollback del apply = revertir código (sin `downgrade`).
Skills: `fastapi`, `test-driven-development`, `python-testing-patterns`.

## Risks / Trade-offs

- [Superficie pública sin auth permite reservas basura] → Mitigación: paciente
  mínimo + turnos `pendiente` que secretaría cancela con motivo; rate-limit si
  trivial (D-04); sin sobreturno por vía pública (D-03); documentado como
  riesgo aceptado v1.0.
- [Token en respuesta `201` visible en demo] → Mitigación: solo en creación,
  nunca en listados; en prod real viaja por WhatsApp (C-06); el plano jamás
  toca DB/logs (D-01).
- [Doble-clic tras confirmar → `404` genérico en vez de `410`] → Mitigación:
  botón deshabilitado tras `200` + log con prefijo de hash (D-06); tabla de
  tokens usados explícitamente fuera de scope.
- [Normalización de teléfono ingenua duplica pacientes] → Mitigación: solo
  dígitos + mínimo 8; duplicados convergibles por secretaría (CRUD pacientes
  C-02); sin verificación por SMS hasta C-06.
- [`GET /confirmar` muta estado (GET no idempotente puro)] → Mitigación:
  decisión consciente por US-011 "confirmar con un link" (apertura desde mail/
  WhatsApp hace GET); el cambio es una transición cerrada y auditada, y el
  token un solo uso impide re-ejecución. Alternativa `POST /confirmar/:token`
  se expone ADEMÁS como alias para clientes programáticos (misma lógica).
- [Expiración derivada vs columna explícita] → Mitigación: D-02 documenta el
  trade-off y deja la puerta abierta a columna explícita en apply con revisión
  humana.

## Migration Plan

1. Mergear solo artefactos openspec (este change: sin código).
2. Apply (TDD): servicio reserva (token+expiración+match paciente, PG real) →
   esquemas estrictos → routers públicos (`POST /reservas`,
   `GET /confirmar/:token` + alias POST, rama pública disponibilidad) →
   frontend (`Reservas`, `Confirmar`, landing `/`, manejo 409/410) → suite
   verde (`pytest backend/app/tests` + checks frontend, PG real, nunca SQLite).
3. Rollback: revertir código; sin `downgrade` (cero migración); hashes
   residuales en turnos demo se invalidan poniendo la columna en NULL.
4. `openspec validate --change c-05-reserva-online-publica --strict` antes de
   archivar; archivar marca `[x]` C-05 en `CHANGES.md` y habilita C-06/C-12 E2E.

## Open Questions

- (D-01/D-06 — revisión humana en apply, no bloquean specs/tasks): ¿`410` para
  reusado/expirado y `404` genérico para desconocido/doble-clic es la
  semántica aceptada por la cátedra?
- (D-02 — revisión humana en apply): ¿expiración derivada
  (`min(created_at+72h, inicio)`) o columna `token_expira_en` explícita?
