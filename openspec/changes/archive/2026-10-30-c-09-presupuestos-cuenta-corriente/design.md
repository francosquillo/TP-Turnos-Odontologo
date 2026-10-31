# Design — c-09-presupuestos-cuenta-corriente

## Context

Ver `proposal.md` (Why). Estado verificado el 2026-10-30:

- La cabeza de Alembic es `005_clinica` (cabeza única).
- `HallazgoOdontograma` es inmutable en lo clínico: corregir da de baja la fila y crea
  otra con `corrige_a_id`. Los `id` son estables (spec `clinica-odontograma-hc`).
- `Tratamiento` es de solo lectura por API, con `precio_base NUMERIC(12,2)`.
- `clinica_servicio` ya ofrece `Actor`, `construir_actor`, `exigir_lectura`,
  `exigir_escritura` y errores de dominio; `clinica_comun.a_http` los traduce a HTTP.
  El servicio hace `flush` y el router hace `commit`.
- `api/cobros.py` es un stub y `test_routers.py` exige que `/cobros` exista.
- `api/pacientes.py` es stub: no hay pantalla de pacientes. La SPA llega al paciente
  desde el turno de la agenda y navega con el estado `pagina` de `App.tsx`.
- **No hay precedentes** de `with_for_update` ni de triggers en el código. Este change
  introduce los dos.
- Los tests usan `Base.metadata.create_all`, no Alembic. Lo que solo exista en la
  migración no existe en esas fixtures.
- Pydantic serializa `Decimal` como texto en JSON. El frontend todavía no maneja dinero.
- El design system está aprobado (Revision 1, `Mode: system-only`).

Restricciones: Pydantic `extra='forbid'`, `Annotated[..., Depends(...)]`, TS sin `any`,
Postgres real, soft-delete (RN-GL-01), sin PHI en logs, datos ficticios.

## Goals / Non-Goals

**Goals:**

- Presupuesto trazable desde hallazgos, con precios que no cambian después de presentar.
- Un cargo por presupuesto aceptado, garantizado por la DB ante concurrencia.
- Saldo imposible de editar: no hay columna y los movimientos son inmutables.
- Contrato claro y mínimo para C-10.

**Non-Goals:**

- Caja, recibos, cobro, cierre diario y transición a `cobrado` (C-10).
- Descuentos, precio manual, ajustes libres de saldo, cobertura de OS.
- Modificar requirements o código de C-04 a C-08, salvo el acceso en la pantalla.

## Decisions

Marcadas **[aprobar]** las que necesitan revisión del usuario antes de apply.

### D-01 — Migración `006_presupuestos_cc`

`revision = "006_presupuestos_cc"`, `down_revision = "005_clinica"`. Crea
`presupuesto`, `item_presupuesto`, `cuenta_corriente` y `movimiento`, más la función y
el trigger de D-12. El downgrade elimina todo, incluida la función. Se usa
`IDENTITY ALWAYS` y `NUMERIC`, como en 005.

Tamaños: `precio NUMERIC(12,2)`, `total` y `monto NUMERIC(16,2)`. Con `cantidad` entre 1
y 99 y hasta 50 ítems, el máximo teórico es ~4,95e13, que entra en `NUMERIC(16,2)` (no
así en `NUMERIC(14,2)`).

### D-02 — Tablas

`presupuesto`: `paciente_id`, `profesional_id` (FK RESTRICT), `estado` (`TEXT + CHECK`),
`total`, `motivo_rechazo`, `presentado_at`, `decidido_at`, `created_at`, `updated_at`,
`deleted_at`, `motivo_baja`. CHECK:

- `ck_presupuesto_estado`: catálogo de 5 estados.
- `ck_presupuesto_total_no_negativo`.
- `ck_presupuesto_rechazo_con_motivo`: `(estado = 'rechazado') = (motivo_rechazo IS NOT NULL)`.
- `ck_presupuesto_baja_con_motivo` y `ck_presupuesto_baja_solo_borrador`.

`item_presupuesto`: `presupuesto_id`, `hallazgo_id`, `tratamiento_id` (FK RESTRICT, todas
NOT NULL), `cantidad`, `precio`. `UNIQUE (presupuesto_id, hallazgo_id, tratamiento_id)`.

Índices sobre toda FK, más `(paciente_id, created_at DESC)` para el historial.

La KB escribe `tratamiento_id/hallazgo_id`. Se interpreta como **ambas** columnas
obligatorias: RN-CL-01 las pide juntas ("pieza FDI + tratamiento").

### D-03 — Transiciones y rutas

```
borrador ──presentar──▶ presentado ──aceptar──▶ aceptado ──(C-10)──▶ cobrado
    │                        └───rechazar──▶ rechazado
    └──baja (lógica)
```

`rechazado` es final: para reintentar se crea otro presupuesto. No hay vuelta de
`presentado` a `borrador`, porque el paciente ya vio esos números.

Rutas: `POST /presupuestos`, `GET /presupuestos?paciente_id&estado`, `GET /:id`,
`PUT /:id`, `POST /:id/{presentar,aceptar,rechazar,baja}`. `PUT` reemplaza los ítems en
vez de un `PATCH` por ítem: es un solo formulario y evita diffs. `presentar` y `baja`
no están en `CHANGES.md`; ver "Diferencias".

### D-04 — Validación de ítems y hallazgos en varios presupuestos **[aprobar]**

Al crear o editar, cada hallazgo debe estar activo y pertenecer a la HC activa del
paciente; un error da `422` con mensaje fijo (no revela si el hallazgo existe en otro
paciente). Vale cualquier hallazgo del paciente, también los de otro profesional,
porque la HC es compartida, y cualquier estado (`ausente` → implante, `sano` → limpieza).

Un hallazgo **puede** estar en varios presupuestos a la vez. Permite ofrecer alternativas
(corona o extracción más implante). El riesgo es aceptar dos alternativas y cobrar
ambas. *Alternativa descartada*: bloquear hallazgos ya presupuestados, que además exige
un lock entre presupuestos y complica rehacer uno rechazado. **Recomendación: permitir.**

### D-05 — Hallazgo corregido después de presupuestar **[aprobar]**

Pendiente que dejó C-08. La corrección **no se bloquea**, porque no se puede frenar un
registro clínico por un presupuesto, y C-08 no cambia.

- `borrador` y `presentado`: `presentar` y `aceptar` revalidan y responden `409`. Un
  `presentado` con hallazgo corregido queda sin salida más que `rechazar`, y el
  odontólogo arma uno nuevo: el paciente ya vio ese documento y no debe mutar.
- `aceptado`: no cambia. La fila original sigue existiendo, por eso no hace falta copiar
  pieza ni cara al ítem. El ítem expone `hallazgo_vigente: false`.

Si se quiere deshacer lo cobrable de un aceptado, va por D-14.

### D-06 — Precio congelado, sin override **[aprobar]**

`item.precio` se copia de `precio_base` en cada alta o reemplazo. El cliente no lo envía
(`extra='forbid'` da `422`). No hay descuentos en v1.0: `CHANGES.md` no los pide, y un
override abre permisos y auditoría. *Alternativa descartada*: `precio` opcional en el
cuerpo.

### D-07 — `total` guardado y calculado

Se conserva la columna de KB y `CHANGES.md`. La recalcula solo el servicio, bajo el lock
de D-13, y los ítems son inmutables fuera de `borrador`, así que no hay deriva por la
API. La regla de saldo derivado aplica a la CC, no a esta columna. *Alternativa
descartada*: calcular con `SUM` en cada lectura; costo y JOIN sin ganancia, ya que el
cargo necesita un valor fijo.

### D-08 — `presentar` exige `total > 0`

`movimiento` no admite monto 0, y el catálogo sí admite `precio_base = 0`. Se corta en
`presentar` con `422`, así `aceptar` siempre tiene un cargo válido y no aparece un
"aceptado sin cargo".

### D-09 — Permisos de presupuestos y vista financiera de admin **[aprobar]**

Matriz de `03`: Admin Ver, Odontólogo CRUD, Secretaria Ver + cobrar. El cobro es C-10.

**Conflicto**: la misma matriz le niega al admin el odontograma, y un ítem contiene
pieza y cara. Se resuelve con vista financiera: el admin ve importes, tratamientos y
estados; `pieza_fdi`, `cara` y `motivo_rechazo` van en `null`. El ocultamiento lo hace
el servicio, con un test por campo. Sigue viendo el nombre del tratamiento, que la
matriz autoriza y que liquidaciones necesita. *Alternativa*: quitarle el acceso, lo que
contradice la matriz. **Recomendación: vista financiera.**

### D-10 — Escritura solo del autor **[aprobar]**

`presentar`, `aceptar`, `rechazar`, `PUT` y `baja` exigen ser el `profesional_id` del
presupuesto y mantener vínculo (`exigir_escritura`), igual que los hallazgos de C-08. La
lectura sigue la regla compartida. Limitación: si el autor deja de atender, nadie más
puede cerrar ese presupuesto; se resuelve creando uno nuevo. *Alternativa*: cualquier
odontólogo vinculado, a costa de que un colega acepte montos que no armó.

### D-11 — `cuenta_corriente` sin saldo, creada al primer movimiento

Columnas: `id`, `paciente_id` UNIQUE, `created_at`. El saldo es
`COALESCE(SUM(monto), 0)` en cada lectura, con índice `(cc_id, created_at)`. `asegurar`
usa `INSERT ... ON CONFLICT (paciente_id) DO NOTHING` seguido de `SELECT`, para el caso
concurrente. `GET` no crea filas.

Consulta: paciente inexistente `404`; paciente dado de baja **sin** cuenta `404`; dado
de baja **con** cuenta `200`, porque la deuda sobrevive a la baja (RN-GL-01).

### D-12 — Movimientos con signo e inmutables por trigger **[aprobar]**

Columnas: `cc_id`, `tipo`, `monto`, `concepto`, `motivo`, `turno_id`, `presupuesto_id`,
`recibo_id`, `anula_a_id`, `creado_por`, `created_at`.

- `ck_movimiento_tipo` y `ck_movimiento_signo`: `cargo > 0`, `pago < 0`, `ajuste <> 0`.
  Más estricto que `monto != 0` de la KB, y compatible con ella.
- `ck_movimiento_anulacion`: `anula_a_id IS NULL OR (tipo = 'ajuste' AND motivo IS NOT NULL)`.
- `creado_por` NOT NULL con FK **RESTRICT**. `SET NULL` dispararía un `UPDATE` y chocaría
  con el trigger; además los usuarios no se borran físicamente.

Trigger `BEFORE UPDATE OR DELETE` que lanza excepción. La regla dura dice "nunca
UPDATE/DELETE", y esto la vuelve imposible también por SQL. Para que exista en los
tests, el modelo adjunta el DDL con `event.listen(Movimiento.__table__, "after_create", ...)`,
y la migración repite los literales; un test compara ambos, como el catálogo de C-08.
Son dos sentencias separadas, porque asyncpg no acepta varias en un `execute`.

`TRUNCATE` y `DROP` no disparan el trigger, así que las fixtures siguen funcionando.
*Alternativa*: confiar en el servicio, más simple pero sin garantía en la DB.

### D-13 — Concurrencia al aceptar

Toda transición y edición toma `SELECT ... FOR UPDATE` sobre el presupuesto y recién ahí
valida el estado. El segundo `aceptar` espera, ve `aceptado` y responde `409`. Red de
seguridad: `UNIQUE (presupuesto_id) WHERE tipo = 'cargo'`; un `IntegrityError` se traduce
a `409`. Implementación: `aceptar` y `anular_cargo` envuelven en `begin_nested()` (savepoint)
solo la creación del movimiento (`asegurar` + `crear_movimiento` en `aceptar`; `crear_movimiento`
del `ajuste` en `anular_cargo`). Un `IntegrityError` sale del savepoint y se traduce a `409`.
El cambio de estado (`actualizar` a `aceptado`) corre después del savepoint, dentro de la misma
transacción: si el cargo falla, la excepción corta antes y el presupuesto queda sin tocar.

Se considera un cargo por presupuesto, no por ítem: la KB dice "cargos" en plural, pero
US-030 habla de "presupuestos aceptados" y un solo cargo hace trivial la unicidad.

### D-14 — Anulación y estado del presupuesto **[aprobar]**

`POST /cuentas/:paciente_id/movimientos/:id/anular` toma `FOR UPDATE` sobre el cargo y
crea un `ajuste` opuesto con `anula_a_id`, `motivo` y `creado_por`. Red de seguridad:
`UNIQUE (anula_a_id) WHERE anula_a_id IS NOT NULL`. Solo se anula un `cargo`: los `pago`
se anulan desde el recibo (C-10) y anular una anulación no tiene sentido. Permiso: solo
`admin`, por la fila Caja de la matriz ("Ver + anular").

**Estado**: el presupuesto sigue `aceptado` con `cargo_anulado: true` derivado, porque
el catálogo de 5 estados es cerrado en KB y `CHANGES.md`. *Alternativa*: agregar un
estado `anulado`, más legible pero fuera de la KB; requiere actualizarla.
**Recomendación: no agregar estado.** Si hubo pagos, el saldo puede quedar a favor, lo
que refleja la realidad; C-10 decide la devolución.

### D-15 — Permisos de cuenta corriente **[aprobar]**

La matriz **no tiene fila** para cuenta corriente. Se deduce de la fila Caja y de
US-030: `secretaria` lee, `admin` lee y anula, `odontologo` sin acceso. *Alternativa*:
odontólogo con vínculo ve el saldo, lo que no pide ninguna US. **Recomendación:
sin acceso**, y agregar la fila a `03_actores_y_roles.md`.

### D-16 — Contrato con C-10

| Elemento | C-09 implementa | C-10 hace |
|---|---|---|
| `recibo_id` | Columna `BIGINT` nula **sin FK** (`recibo` no existe) | Agrega la FK e índice en su migración |
| `tipo = 'pago'` | Admitido por CHECK con signo negativo, leído en saldo | Lo escribe con `recibo_id` |
| Estado `cobrado` | Admitido por CHECK, sin ruta | Define cuándo y lo aplica |
| `concepto` | Texto fijo sin PHI | Mantiene el criterio |
| Repo de cuentas | `asegurar`, `saldo`, `crear` | Los reutiliza |
| Anulación de `pago` | `409` en la ruta de C-09 | La hace `POST /recibos/:id/anular` con un `ajuste` y `anula_a_id` |

Avisos para C-10: el trigger impide completar `recibo_id` después, así que el pago debe
nacer con él. El cargo es por el total, sin descontar cobertura de OS. El bloqueo de
RN-CO-01 no alcanza a C-09, porque aceptar no mueve caja; C-10 confirma ese límite.

### D-17 — `turno_id`

`movimiento.turno_id` es FK nula RESTRICT y **C-09 no la llena**: el cargo nace del
presupuesto, y `Presupuesto` no tiene turno en KB ni `CHANGES.md`. Queda para cargos
por prestación de C-10 o C-11. La dependencia real de C-04 es otra: `existe_vinculo`, los
permisos del odontólogo y la FK.

### D-18 — Soft-delete

`presupuesto`: baja lógica solo en `borrador`, con motivo. Un `presentado` se resuelve
con `rechazar`. `item_presupuesto`: en un `borrador` se reemplazan **físicamente** **[aprobar]**;
un borrador no tiene efecto legal ni contable, y los ítems no son historia clínica.
RN-GL-01 dice "toda eliminación", por eso se marca. `cuenta_corriente` y `movimiento`:
nunca se eliminan.

### D-19 — Capas y reutilización

`servicios/presupuesto_servicio.py` y `servicios/cuenta_servicio.py` reutilizan `Actor`,
`construir_actor`, los errores y `a_http` de C-08, sin copiarlos. Se agrega un helper de
lectura que deja pasar a `admin` y delega en `exigir_lectura`. Los routers siguen el
patrón C-08: `flush` en el servicio, `commit` en el router. `api/cobros.py` no se toca.
`/cuentas` usa `require_role("secretaria", "admin")`; `anular`, `require_role("admin")`.

### D-20 — Sin PHI

Mensajes de error fijos, sin log de motivos ni ítems. `concepto = "Presupuesto {id}"`.
`motivo_rechazo` y los motivos van en el cuerpo, nunca en la URL. El test de C-08 se
extiende a estas rutas, y cada feature tiene su test `sin-consola`.

### D-21 — Frontend

- `features/presupuestos`: `PresupuestosPanel` se carga con `lazy` desde `OdontogramaPage`
  y recibe los hallazgos activos ya cargados, sin otro fetch. `PresupuestoForm` usa
  `GET /tratamientos`. `PresupuestoDetalle` es de solo lectura y se reutiliza desde CC.
- `features/cuenta-corriente`: `CuentaPage` se abre con un botón nuevo en `TurnoCard`
  (prop opcional `alAbrirCuenta`, patrón de `alAbrirOdontograma`), para `secretaria` y
  `admin`. `App.tsx` suma las páginas `cuenta` y su `RequireRole`.
- `shared/moneda.ts`: formatea el texto decimal con `Intl.NumberFormat("es-AR")`. Sin
  aritmética de dinero en el cliente: el total siempre lo da el servidor.
- `shared/api-json.ts`: extrae `pedir`, `errorDe` y `detalleDe` de `odontograma/api.ts`,
  para no duplicarlos dos veces más. Los tests de odontograma son la red de seguridad.
- Estilos en `frontend/src/styles/`, como `odontograma.css`, solo con variables de
  `tokens.css`. Sin colores nuevos: los estados usan tokens semánticos existentes
  (`--color-info-*`, `--color-success-*`, `--color-danger-*`, `--color-warning-*`) con
  texto visible. Si hiciera falta un token nuevo, se sube la `Revision`.
- `react`: fetches independientes con `Promise.all`, estado derivado en render, sin
  definir componentes dentro de componentes.

## UI Mockups

- Design system revision: 1
- Decision: no (project policy)
- Date: 2026-10-30
- Approval del sistema: approved (2026-10-28, by user)

Las tareas de frontend usan `design-system/tokens.css`. No hay mockups por change
(`Mode: system-only`, coincide en `.active-orchestrator-state.json` y `README.md`).

## Diferencias entre CHANGES.md y la KB

| # | Diferencia | Resolución |
|---|---|---|
| 1 | `CHANGES.md` no lista una ruta para llegar a `presentado` | Se agrega `presentar` (D-03) |
| 2 | "CRUD" sugiere `DELETE`, pero RN-GL-01 exige baja lógica | `POST /:id/baja`; `DELETE` da `405` |
| 3 | "Anulación vía contramovimiento" no tiene endpoint | Se agrega `anular` (D-14) |
| 4 | Matriz: admin ve presupuestos pero no odontograma | Vista financiera (D-09) |
| 5 | Matriz sin fila de cuenta corriente | Se deduce (D-15); actualizar `03` |
| 6 | KB: `concepto` en `Movimiento`; `CHANGES.md` no lo nombra | Se usa la KB |
| 7 | KB: `monto != 0`, sin regla de signo | CHECK por tipo, compatible (D-12) |
| 8 | KB: "cargos" en plural (Flujo 3) | Un cargo por presupuesto (D-13) |
| 9 | Regla dura `tarjeta_simulada`; KB `tarjeta` en `MovimientoCaja` | No afecta a C-09; para C-10, prevalece la regla dura |
| 10 | `api/cobros.py` dice "caja real en C-09/C-10" | La caja es solo C-10; stub intacto |

## Risks / Trade-offs

- [Primer `FOR UPDATE` y primer trigger del repo] → Test concurrente con dos sesiones
  reales y test de paridad entre modelo y migración.
- [Trigger ausente en tests] → DDL `after_create` en el modelo; test de `UPDATE` rechazado.
- [Cambio de cabeza rompe tests] → `test_c08_cabeza_unica_005_sobre_004` y el downgrade
  de C-08 exigen ajuste; se hace en la misma task que la migración.
- [Dos alternativas aceptadas para un hallazgo] → D-04; la anulación de D-14 lo corrige.
- [`presentado` bloqueado por un hallazgo corregido] → D-05; se rechaza y se rehace.
- [`SUM` por lectura] → Índice `(cc_id, created_at)`; volumen de TP, sin paginación.
- [Autor ausente] → D-10; se crea otro presupuesto.
- [Ocultamiento de admin omitido en una ruta nueva] → Una sola función de armado de
  respuesta, con test por campo.

## Migration Plan

1. `alembic upgrade head` aplica 006; solo agrega tablas y no toca datos previos.
2. Reversión: `alembic downgrade 005_clinica`. Datos ficticios.
3. Sin seed nuevo: los tratamientos y usuarios de C-08 alcanzan.
