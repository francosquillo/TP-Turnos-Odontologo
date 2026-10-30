# Design — c-08-clinica-odontograma-hc

## Context

Ver `proposal.md` (Why). Estado verificado el 2026-10-30:

- `backend/alembic/versions/` tiene 001, 002, 003 y `004_espera` (cabeza única).
- `api/clinica.py` es el stub de C-01 y `test_routers.py` exige que `/clinica` exista.
- `api/pacientes.py` también sigue siendo stub: **no hay listado ni buscador de
  pacientes**. El único lugar de la SPA con `paciente_id` y nombre es la agenda.
- No existe `POST /admin/usuarios`, y el seed no crea usuarios `odontologo` ni
  `secretaria`. El profesional demo tiene `usuario_id = NULL`.
- `Profesional.usuario_id` y `ProfesionalRepository.por_usuario_id` ya existen.
- `Paciente` tiene `deleted_at`; las bajas con motivo usan `POST /:id/baja` (C-07).
- Los tests contra Postgres crean el esquema con `Base.metadata.create_all`, no
  con Alembic: lo que cargue la migración no existe en esas fixtures.
- La SPA no usa router: `App.tsx` navega con estado `pagina`.

Restricciones: Pydantic `extra='forbid'`, `Annotated[..., Depends(...)]`, TS sin
`any`, Postgres real, soft-delete (RN-GL-01), sin PHI en logs, datos ficticios.

## Goals / Non-Goals

**Goals:**

- HC única por paciente, con alergias presentes en toda respuesta clínica.
- Odontograma FDI correcto en API y en DB, con historial por pieza completo.
- Catálogo de estados cerrado y versionado; catálogo de tratamientos de lectura.
- Contrato estable de `hallazgo.id` y `tratamiento.id` para C-09.
- Feature usable de punta a punta con los datos del seed.

**Non-Goals:**

- Dentición temporal, periodontograma, imágenes, firma digital.
- Presupuestos (C-09), ABM de tratamientos o usuarios (C-12), pantalla de pacientes.
- Restaurar una HC dada de baja (D-06) y nota de evolución en texto libre (D-14).
- Modificar `agenda_servicio`, EXCLUDE o contratos C-04..C-07.

## Decisions

### D-01 — Migración `005_clinica` (corrige "Migración 003" de CHANGES.md)

`CHANGES.md` dice "Migración 003", pero está desactualizado: 003 es
`003_notificacion` y la cabeza actual es `004_espera`. Este change usa
`backend/alembic/versions/005_clinica.py`, `revision = "005_clinica"`,
`down_revision = "004_espera"`. No se edita `CHANGES.md` en este change.

La migración nueva rompe supuestos de tests existentes, que se ajustan en la
misma task:

| Archivo | Cambio |
|---|---|
| `test_c07_migracion.py` | La cabeza deja de ser `004_espera`/`005_espera`: pasa a validar que `004_espera` está en la cadena y que la cabeza es única. |
| `test_c05_reserva_pg.py` | Suma `005_clinica.py` a la lista exacta. |
| `db_utils.py` | `reset_estado_base` suma las 4 tablas nuevas. Sin esto, un residuo de `create_all` rompe `upgrade head` con `DuplicateTableError`. |

Rollback: `alembic downgrade -1` (solo datos ficticios).

### D-02 — FDI: lista exacta, no rango

La KB escribe "11–48", pero ese rango incluye 19, 20, 29, 30, 39 y 40, que no son
piezas. Se validan exactamente 11–18, 21–28, 31–38 y 41–48, en tres puntos:

- DB: `pieza_fdi SMALLINT NOT NULL`, `CHECK (pieza_fdi BETWEEN 11 AND 48 AND
  pieza_fdi % 10 BETWEEN 1 AND 8)` (`ck_hallazgo_pieza_fdi_valida`).
- Esquema: tipo `PiezaFdi` compartido por cuerpos de alta y corrección (`422`).
- Query: el filtro `?pieza=` usa el mismo tipo.

Dentición temporal (51–85) fuera de v1.0: la KB no la incluye.

### D-03 — Caras: KB + `pieza_completa`, validadas por arcada (desvío de la KB)

RN-CL-03 exige cara, pero `ausente`, `implante` y `corona` no ocurren en una cara.
Sin un valor de pieza entera, el odontólogo tendría que elegir una cara al azar.
Alternativa descartada: `cara` nullable, porque contradice "FDI + cara" y deja
ambiguo si falta el dato o es toda la pieza.

Valores: `oclusal, mesial, distal, vestibular, palatina, lingual, raiz,
pieza_completa` (`TEXT + CHECK`: conjunto anatómico fijo, no se versiona).

- `palatina` solo en 1x/2x y `lingual` solo en 3x/4x, en esquema y en DB
  (`ck_hallazgo_cara_arcada`). Es un chequeo barato que evita datos falsos.
- `incisal` no se agrega: en incisivos y caninos, `oclusal` representa el borde
  incisal y la UI lo rotula "Incisal". El valor guardado no cambia.

### D-04 — Catálogo de estados: tabla versionada cargada por migración

La KB pide "catálogo cerrado versionado" y deja abierta la forma, y su lista
termina en "etc.". Se usa una tabla `estado_hallazgo_catalogo`:

```
id BIGINT IDENTITY PK, codigo TEXT, version SMALLINT, nombre TEXT,
alcance TEXT CHECK IN ('cualquiera','pieza'), vigente BOOLEAN NOT NULL,
UNIQUE (codigo, version)
```

- `hallazgo_odontograma (estado, catalogo_version)` es FK compuesta hacia ese
  UNIQUE: el dato sigue legible y la DB impide valores fuera de catálogo.
- "Cerrado": la API no escribe. Una versión nueva es una migración que marca
  `vigente = false` en las filas anteriores e inserta las nuevas.
- El servidor sella `catalogo_version`; el cliente no la envía.
- V1 son los 7 valores nombrados en la KB; el "etc." se cierra sin inventar nada.
  `alcance = pieza`: `corona, endodoncia, implante, ausente`.
  `alcance = cualquiera`: `sano, caries, obturacion`.
- La regla alcance/cara vive en el servicio (`422`): llevarla a DB requeriría un
  trigger y no vale la pena con una sola vía de escritura.

Alternativas descartadas: `TEXT + CHECK` (no registra bajo qué versión se cargó el
dato) y enum SQL (la skill lo desaconseja para valores que evolucionan).

**Carga**: la migración hace `bulk_insert` para que el catálogo exista sin seed.
Los tests usan `create_all`, por eso `CATALOGO_ESTADOS_V1` vive como constante en el
modelo y un helper en `db_utils.py` la inserta. Un test compara constante y
migración. La migración repite los literales: no importa modelos.

### D-05 — Hallazgos sin sobrescritura: corrección = baja + fila nueva

La KB no define cómo convive el historial con la edición, y un `UPDATE` destruiría
justo lo que CA-2 de US-020 pide conservar.

- Campos clínicos inmutables. Una evolución real (caries → obturación) es un
  hallazgo nuevo; el estado vigente es el más reciente por `(pieza, cara)`.
- `PUT` es la corrección de un error: da de baja la fila con `motivo` y crea otra
  con `corrige_a_id`, en una transacción. Devuelve `200` con el `id` nuevo.
- `POST .../:id/baja` para lo cargado por error. Sin `DELETE` físico.
- `uq_hallazgo_corrige_a` (UNIQUE parcial en `corrige_a_id IS NOT NULL`) impide dos
  correcciones de la misma fila ante una carrera; el `IntegrityError` da `409`.
- `ck_hallazgo_baja_con_motivo`: `(deleted_at IS NULL) = (motivo_baja IS NULL)`.
- Auditoría (RN-GL-02): solo el autor puede dar de baja (D-07), así que
  `profesional_id` + `deleted_at` + `motivo_baja` ya dicen quién, cuándo y por qué.

Tabla `hallazgo_odontograma`: `id, hc_id FK RESTRICT, pieza_fdi, cara, estado,
catalogo_version, fecha TIMESTAMPTZ NOT NULL, profesional_id FK RESTRICT,
corrige_a_id FK self nullable, deleted_at, motivo_baja`. `fecha` la fija el servicio
con reloj Python para poder usar `freezegun`. Orden: `fecha DESC, id DESC`.

Índices: `ix_hallazgo_hc_pieza (hc_id, pieza_fdi)`, `ix_hallazgo_profesional_id`,
`ix_hallazgo_estado_version (estado, catalogo_version)`, `uq_hallazgo_corrige_a`.

### D-06 — HC: UNIQUE total y sin restauración (confirmada por el usuario, 2026-10-30)

`historia_clinica`: `id, paciente_id UNIQUE FK RESTRICT, antecedentes TEXT NULL,
alergias TEXT NULL, deleted_at, motivo_baja, created_at, updated_at`, con límites
`CHECK length` (antecedentes 10000, alergias 2000, igual en esquema) y
`ck_hc_baja_con_motivo`.

- `paciente_id` UNIQUE total, no parcial: una HC nueva tras una baja dejaría el
  historial clínico partido en dos.
- La baja no toca los hallazgos: quedan inaccesibles porque la HC da `404`.
- Consecuencia aceptada: **no hay restauración por API**, y `POST /historias` da
  `409` para ese paciente. Revertir una baja errónea requiere SQL. Agregar
  `POST /historias/:id/restaurar` es barato si se quiere (ver Open Questions).

### D-07 — Lectura de "CRUD propios" y matriz por endpoint (confirmada por el usuario, 2026-10-30)

La fila `Odontograma/HC` dice Admin `—`, Odontólogo `CRUD propios`, Secretaria `Ver`,
y la KB no define "propios". Una HC es del paciente, no del profesional, así que:

- **Paciente propio**: el odontólogo tiene al menos un turno no `cancelado` con ese
  paciente, en cualquier fecha. Un paciente con dos odontólogos comparte una HC y
  ambos ven todo: atender sin ver lo que hizo el otro sería un riesgo clínico.
- **Hallazgo propio**: lo creó ese profesional. Solo el autor corrige o da de baja.

| Endpoint | admin | secretaria | odontologo |
|---|---|---|---|
| `GET /historias?paciente_id=`, `GET /historias/:id` | 403 | sí | vinculado |
| `POST /historias`, `PATCH /historias/:id`, `POST /historias/:id/baja` | 403 | 403 | vinculado |
| `GET /odontograma/:hc_id/hallazgos`, `GET .../:id` | 403 | sí | vinculado |
| `POST /odontograma/:hc_id/hallazgos` | 403 | 403 | vinculado |
| `PUT .../:id`, `POST .../:id/baja` | 403 | 403 | autor y vinculado |
| `GET /odontograma/catalogo`, `GET /tratamientos` | sí | sí | sí |

- Admin queda fuera de los datos clínicos, como dice la matriz, y eso también vale
  para el alias Dueño. Los catálogos no llevan PHI y C-11/C-12 los van a necesitar.
- La secretaria ve antecedentes y alergias: lo dice la matriz. Es amplio frente a
  la minimización de RN-GL-03, aceptable con datos ficticios; revisar al escalar.
- Odontólogo sin `Profesional` vinculado: `403`, también en lectura.
- Sin vínculo: `403` (igual que `api/turnos.py`).
- `GET /historias` exige `paciente_id` y devuelve una lista de 0 o 1 fila, para no
  exponer un listado masivo de PHI que ninguna pantalla necesita.

Rol con `require_role` en el router; vínculo y autoría en el servicio. El vínculo se
resuelve con un método nuevo `TurnoRepository.existe_vinculo(profesional_id,
paciente_id)`, aditivo. `_profesional_propio_id` se reutiliza desde `api/turnos.py`.

### D-08 — Alergias: siempre presentes y `null` = no relevadas

CA-1 de US-021 dice "visibles siempre", sin precisar dónde. Se aplica a toda
respuesta de `/historias` y `/odontograma/:hc_id/hallazgos`:

- `HistoriaOut` trae `alergias` como campo.
- Listado: `{alergias, hallazgos: [...]}`. Alta, detalle, corrección y baja:
  `{alergias, hallazgo: {...}}`.

`null` significa "no relevadas" y nunca se confunde con "sin alergias": un campo
vacío que se lee como "no tiene" es un riesgo clínico. Texto vacío se normaliza a
`null`. Quien sabe que no hay alergias lo escribe ("Sin alergias conocidas").

### D-09 — Routers nuevos; el stub `/clinica` queda

`CHANGES.md` fija `/historias`, `/odontograma` y `/tratamientos` en la raíz, pero el
stub usa prefijo `/clinica`, y moverlos a `/clinica/...` contradiría la KB. Se crean
`api/historias.py`, `api/odontograma.py` y `api/tratamientos.py`, registrados en
`main.py`. `api/clinica.py` no se toca porque `test_routers.py` lo exige; retirarlo
es limpieza aparte.

Agregado al scope: `GET /odontograma/catalogo`, para que el frontend no duplique el
catálogo cerrado.

Códigos: `401` sin Bearer, `403` rol/vínculo/autoría, `404` inexistente o dado de
baja (incluye hallazgo de otra HC), `409` duplicado o ya dado de baja, `422`
validación.

Capas: `clinica_servicio.py` tiene las reglas y solo hace `flush`; el router es dueño
del `commit` (patrón C-07). Modelos: un archivo por entidad, con el catálogo de
estados dentro de `hallazgo_odontograma.py`. Esquemas en `esquemas/clinica.py`.

### D-10 — `Tratamiento` y contrato con C-09

`tratamiento`: `id BIGINT IDENTITY, codigo TEXT UNIQUE, codigo_nomenclador TEXT NULL,
nombre TEXT, precio_base NUMERIC(12,2) CHECK >= 0, created_at`.

- `codigo_nomenclador` es texto sin FK: `Arancel` recién existe en C-11.
- La API solo lee; no hay cambio de precio, y por eso aún no aplica la auditoría de
  aranceles de RN-GL-02.
- Sin relación directa hallazgo↔tratamiento. La KB dibuja `Hallazgo *──*
  Tratamiento`, pero esa relación es `ItemPresupuesto` de C-09: una tabla puente
  ahora quedaría vacía o la duplicaría.

Contrato para C-09: `hallazgo.id` y `tratamiento.id` son estables y las filas no se
borran. C-09 debe rechazar ítems nuevos sobre hallazgos con `deleted_at` y decidir
qué hacer con un presupuesto cuyo hallazgo se corrige (`corrige_a_id` permite
seguir la cadena). C-08 no bloquea esas bajas, porque aún no existe la referencia.

### D-11 — Usuarios demo en el seed (agrega scope)

Con D-07 ni el admin puede operar la feature, y no hay API para crear usuarios: sin
esto C-08 no se puede usar ni mostrar. `seed.py` suma:

- `seed_tratamientos`: 6 tratamientos ficticios, idempotente por `codigo`, sin pisar
  filas existentes.
- `seed_usuarios_demo`: `odontologo.demo@example.com` y `secretaria.demo@example.com`,
  con `SEED_ADMIN_PASSWORD` hasheada con Argon2 (sin secreto nuevo ni contraseña en
  código). Vincula al odontólogo con el profesional demo solo si `usuario_id` es NULL.

No se crea paciente demo: los turnos existentes o la reserva pública ya los generan.

### D-12 — Sin PHI en logs

- Ningún `_log.*` del flujo clínico interpola antecedentes, alergias, motivos ni
  campos de hallazgo. Solo ids cuando haga falta.
- `motivo` viaja en el cuerpo, nunca en query, para que no aparezca en access logs.
- Test `caplog` en nivel DEBUG con marcadores ficticios, en éxito y en `422`.
- Frontend: test que falla si `features/odontograma` contiene `console.`.
- El flujo clínico no toca `notificacion_servicio` (RN-CL-04, RN-NO-04).

### D-13 — Frontend: entrada desde la agenda y sin tokens nuevos

- **Entrada**: botón en `TurnoCard` visible para `odontologo` y `secretaria`, porque
  no hay pantalla de pacientes. `App.tsx` suma la página `odontograma` y guarda
  `{pacienteId, pacienteNombre}`. Sin router nuevo.
- **Carga**: `React.lazy` para `OdontogramaPage`; catálogo e HC con `Promise.all`.
- **Estado vigente**: función pura en `tipos.ts`, derivada en render desde los
  hallazgos activos. La fila `pieza_completa` más reciente tapa a las de cara más
  antiguas. Los filtros de caras por pieza y estado también son funciones puras.
- **Estilo**: `styles/odontograma.css` importa valores solo por `var(--...)` desde
  `styles/tokens.css`, y reutiliza `.btn`, `.badge`, `.field`, `.input` y `.banner`
  de `design-system/components.html`. Las clases que ya estén en
  `styles/lista-espera.css` no se duplican.
- **Sin tokens nuevos**: tocar `tokens.css` obligaría a subir de Revision 1. Los
  estados se mapean a variables existentes (`--estado-*`, `--espera-*`,
  `--color-danger*`) y siempre llevan texto, porque el color nunca informa solo.
- **Responsive**: un cuadrante por fila en móvil (390 px), los cuatro en cruz en
  escritorio; objetivo táctil de 44 px; cada pieza es `<button>` con `aria-label`.
- Nombre y logo siguen `(TBD)`.

### D-14 — "Evolución" de US-021 = historial de hallazgos (confirmada por el usuario, 2026-10-30)

US-021 pide "antecedentes, alergias y evolución", pero el modelo de la KB y
`CHANGES.md` no tienen ese campo y los CA tampoco lo exigen. En v1.0 la evolución es
la línea de tiempo de hallazgos. No se agrega nota libre; si la cátedra la pide,
sería una columna `nota` en hallazgo o una tabla propia, en otro change.

### D-15 — `verify` y TDD con Postgres real

Las tasks RED/GREEN de DB necesitan Postgres del compose. La regla dura pide permiso
explícito y Docker Desktop para el `verify`; el apply debe pedir ese permiso antes de
levantar servicios y bajarlos al terminar. `freezegun` se usa en `fecha` y `updated_at`.

### D-16 — Desvíos y decisiones del apply (2026-10-30)

- `HallazgoOut` suma `es_propio: bool`, calculado por el servidor según quién consulta.
  La SPA no conoce su `profesional_id` (`/auth/me` no lo expone y no se toca el
  contrato de C-03) y la regla "baja solo en hallazgos propios" (D-13) lo necesita.
- Los hallazgos se piden siempre con `incluir_anulados=true` y el estado vigente y el
  historial se derivan en el cliente (una sola petición por historia).
- Los tests API usan Postgres real con la app real (`get_db` sobre la sesión del test),
  no fakes; se confirma el mundo sembrado antes porque los routers hacen `rollback`.
- `vite.config.ts`: `test.css.include` procesa solo `odontograma.css`, para que el test
  de "sin colores literales" pueda leerlo con `?raw`.
- `test_c06_notificacion_modelo.py`: el regex de `down_revision` cruzaba líneas y
  malinterpretaba el docstring de `004_espera`; se acotó a una línea (hallado al sumar 005).
- Los seeds demo comparten la contraseña `SEED_ADMIN_PASSWORD` (D-11); `run_seed` exige que
  no esté vacía.

## Risks / Trade-offs

- [Odontólogo sin turno previo no puede abrir una HC] → Aceptado: la secretaria crea
  el turno. Flujo 3 siempre parte de un turno.
- [Un paciente con turno futuro ya da acceso a su HC] → Aceptado: permite preparar la
  consulta.
- [Secretaria lee antecedentes completos] → Viene de la matriz; revisar con RN-GL-03.
- [Baja de HC irreversible por API] → D-06, decisión a revisar.
- [Catálogo en dos lugares (constante y migración)] → Test que los compara (D-04).
- [Sin nota de evolución] → D-14, decisión a revisar.
- [Corrección de un hallazgo ya presupuestado] → Se resuelve en C-09 (D-10).
- [Contraseña compartida con admin en usuarios demo] → Solo demo local con datos
  ficticios; C-12 reemplaza el flujo.
- [El stub `/clinica` sigue respondiendo] → Deuda menor conocida (D-09).

## Migration Plan

1. Mergear solo artefactos openspec (este change no trae código).
2. Apply en el orden de `tasks.md`: modelos + `005_clinica` → esquemas → repos →
   servicio → routers → seed → PHI → frontend → verificación.
3. Rollback: revertir código + `alembic downgrade -1`. Borra tablas nuevas (solo
   datos ficticios). Los usuarios demo quedan: son inofensivos.
4. `openspec validate c-08-clinica-odontograma-hc --strict` antes de archivar.

## Open Questions

Ninguna. El usuario revisó y APROBÓ tal como estaban propuestas, el 2026-10-30,
las decisiones D-06, D-07, D-11 y D-14 (confirmadas por el usuario):

- D-06 (confirmada): sin `POST /historias/:id/restaurar` en v1.0.
- D-07 (confirmada): "propio" = al menos un turno no cancelado, cualquier fecha; HC
  compartida; solo el autor corrige o anula; admin/Dueño `403` en datos clínicos;
  la secretaria lee antecedentes y alergias.
- D-11 (confirmada): el seed suma `odontologo.demo@example.com` y
  `secretaria.demo@example.com`.
- D-14 (confirmada): el historial de hallazgos es la evolución, sin nota libre.

## UI Mockups

- Design system revision: 1 (design-system/README.md, aprobado 2026-10-28)
- Decision: no (project policy) — modo system-only, 2026-10-30
