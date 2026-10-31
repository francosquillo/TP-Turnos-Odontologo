# Design — c-10-caja-cobros-simulados

## Context

Ver `proposal.md` (Why). Estado verificado el 2026-10-31:

- La cabeza de Alembic es `006_presupuestos_cc` (cabeza única).
- `movimiento.recibo_id` es `BIGINT` nula sin FK. El trigger `trg_movimiento_inmutable`
  prohíbe `UPDATE` y `DELETE` por fila.
- Ninguna ruta escribe `pago` ni `cobrado`. Los `pago` solo existen en tests, algunos sin
  recibo y otros con `recibo_id` inventado.
- **No hay tabla de auditoría.** El patrón del repo es guardar autor, fecha y motivo en la
  fila (`creado_por`, `motivo_sobreturno`, `motivo_baja`).
- La zona horaria está repetida como constante en tres servicios y en
  `Settings.tz`. Los `created_at` usan `now()` de la DB, que `freezegun` no congela.
- `a_http` busca el error con `_STATUS[type(error)]`: **una subclase de `ConflictoError`
  daría `KeyError`**. C-10 usa los tipos existentes, sin subclases.
- `fetchConAuth`, `pedir`, `MotivoForm` y `formatearMoneda` ya existen. La SPA navega con
  el estado `pagina` de `App.tsx`.
- `/cobros` es un stub de C-01 y `test_routers.py` exige que exista.
- Los tests usan `Base.metadata.create_all`: lo que solo esté en la migración no existe
  en esas fixtures.

Restricciones: Pydantic `extra='forbid'`, `Annotated[..., Depends(...)]`, TS sin `any`,
Postgres real, sin PHI en logs ni URLs, datos ficticios.

## Goals / Non-Goals

**Goals:**

- Numeración de recibos sin huecos, con garantía en la transacción.
- Un cobro nunca queda a medias: recibo, `pago` y movimiento de caja nacen juntos.
- RN-CO-01 garantizado por el servicio y por la DB.
- Caja cerrada y recibos protegidos también ante SQL directo.
- Las 9 obligaciones del contrato de C-09 resueltas (tabla de D-21).

**Non-Goals:**

- PDF del recibo (D-19), egresos y fondo inicial de caja (D-18).
- Pagos a cuenta sin presupuesto (D-08) y devoluciones fuera de la anulación.
- Cierre automático por worker: `08` menciona "cierres" en el cron, pero un cierre exige
  un conteo humano. Reapertura de caja (D-07).
- Cobertura de obra social (D-20).
- Corregir `GET /health` o las horas UTC de la agenda.

## Decisions

Las decisiones de esta tabla necesitan aprobación del usuario antes de apply. Por ser
governance CRITICO, ninguna tarea arranca sin esa aprobación. El usuario aprobó el
2026-10-31 las doce tal como se recomendaron.

| Decisión | Tema | Recomendación | Estado |
|---|---|---|---|
| D-05 | Apertura | Implícita con el primer movimiento | Aprobada 2026-10-31 |
| D-06 | Alcance del bloqueo | Solo cobrar y anular recibos | Aprobada 2026-10-31 |
| D-07 | Caja cerrada | No se reabre; cobros del día siguen mañana | Aprobada 2026-10-31 |
| D-08 | Imputación | A un presupuesto, con parciales y sin sobrepago | Aprobada 2026-10-31 |
| D-09 | `cobrado` | Al llegar a cero; vuelve a `aceptado` si se anula | Aprobada 2026-10-31 |
| D-12 | Cierre | Un solo total contado, con desglose informativo | Aprobada 2026-10-31 |
| D-13 | Anulación | Cae en la caja de hoy; exige caja operable | Aprobada 2026-10-31 |
| D-15 | `pago` con recibo | CHECK en la DB; ajusta tests de C-09 | Aprobada 2026-10-31 |
| D-16 | Permisos | Matriz literal: admin no cobra ni cierra | Aprobada 2026-10-31 |
| D-18 | Egresos | Fuera de alcance | Aprobada 2026-10-31 |
| D-19 | PDF | Fuera de alcance; comprobante en pantalla | Aprobada 2026-10-31 |
| D-25 | Idempotencia del cobro | Clave del cliente en el cuerpo, UNIQUE en `recibo` | Aprobada 2026-10-31 |

### D-01 — Migración `007_caja_recibos`

`revision = "007_caja_recibos"`, `down_revision = "006_presupuestos_cc"`. Crea `caja`,
`recibo`, `recibo_contador` y `movimiento_caja`, con sus funciones y triggers (D-14). `recibo`
nace con `clave_idempotencia` y sus dos restricciones (D-25). Sobre `movimiento` agrega la FK `fk_movimiento_recibo` (RESTRICT), `ix_movimiento_recibo_id`,
`uq_movimiento_pago_recibo` (`recibo_id` único `WHERE tipo = 'pago'`) y
`ck_movimiento_pago_con_recibo`.

`ADD CONSTRAINT` no actualiza filas, así que no choca con el trigger de `movimiento`. La
migración falla si hay un `pago` con recibo inválido en una base local: se prefiere el
error a un dato sin recibo. El downgrade quita lo agregado y borra tablas y funciones.
No revierte el estado `cobrado` ni borra pagos, porque `movimiento` es inmutable; son
datos ficticios y 006 admite esas filas.

### D-02 — Tablas

`caja`: `id`, `fecha DATE` UNIQUE, `abierta_por`, `estado`, `total_sistema`, `total_contado`,
`diferencia`, `motivo_diferencia`, `cerrada_por`, `cerrada_at`, `created_at`. Totales
`NUMERIC(18,2)`, porque suman montos de `NUMERIC(16,2)`.

- `ck_caja_estado`: `abierta | cerrada`.
- `ck_caja_cierre_completo`: cerrada exige totales, autor y fecha; abierta los exige nulos.
- `ck_caja_diferencia`: `diferencia = total_contado - total_sistema`.
- `ck_caja_diferencia_con_motivo`: `diferencia = 0 OR motivo_diferencia IS NOT NULL`.
- `ck_caja_contado_no_negativo`.
- `uq_caja_una_abierta`: `UNIQUE (estado) WHERE estado = 'abierta'`.

`total_sistema` puede ser negativo: un día puede tener solo reversiones (D-13).

`recibo`: `id`, `numero BIGINT` UNIQUE, `paciente_id`, `monto NUMERIC(16,2)`, `medio`,
`emitido_por`, `clave_idempotencia TEXT NOT NULL` (D-25), `anulado BOOLEAN NOT NULL DEFAULT
false`, `motivo_anulacion`, `anulado_por`, `anulado_at`, `created_at`. CHECK de monto
positivo, de medio, y `ck_recibo_anulacion` (anulado si y solo si tiene motivo, autor y
fecha). `uq_recibo_clave_idempotencia` y `ck_recibo_clave_formato`, ver D-25.

`movimiento_caja`: `id`, `caja_id`, `recibo_id` NOT NULL, `medio`, `monto` con signo
(`<> 0`), `motivo`, `creado_por`, `created_at`. `ck_movcaja_reversion_con_motivo`:
`monto > 0 OR motivo IS NOT NULL`. `uq_movcaja_ingreso` y `uq_movcaja_reversion`: un
ingreso y como máximo una reversión por recibo (índices únicos parciales por signo).

`recibo` no guarda `caja_id`: se llega por `movimiento_caja`, sin duplicar el dato. Todas
las FK son RESTRICT y llevan índice. Autor y fechas de anulación vienen de RN-GL-02 y ya
figuran en `04`.

### D-03 — Medios: prevalece `tarjeta_simulada`

Regla dura y US-031 ganan sobre `tarjeta` en `04`. Se usa `TEXT + CHECK`, como el resto del
repo, con un `Literal` en el esquema. `04` ya está corregido.

### D-04 — Día operativo

`hoy_operativo()` en `caja_servicio`: `datetime.now(ZoneInfo(get_settings().tz)).date()`.
Es el único lugar que decide el día. No se usa `CURRENT_DATE`, que depende de la zona de
la sesión y que `freezegun` no controla. El cliente nunca envía la fecha de un cobro.
Argentina no tiene horario de verano, pero no se asume UTC-3 fijo.

Tests: `freezegun` en `2026-10-31 02:59:59Z` (30/10 local) y `03:00:00Z` (31/10 local). Por
lo dicho en Context, las aserciones usan `caja.fecha`, nunca `created_at`.

### D-05 — Apertura implícita **[aprobada 2026-10-31]**

No hay endpoint de apertura: la matriz y `CHANGES.md` no lo piden. La caja nace con el
primer movimiento, y `abierta_por` es quien lo generó. Puede ser un admin si lo primero
del día es una anulación (D-13).

Consecuencias: un día sin movimientos no tiene caja ni exige cierre. No hay fondo inicial.

*Alternativa*: `POST /caja/abrir` explícito por la secretaria al empezar el día. Registra
mejor quién abrió, pero agrega un paso diario y un estado más para el bloqueo.

### D-06 — Alcance y mecanismo del bloqueo **[aprobada 2026-10-31]**

Interpretación de RN-CO-01: "operar" significa **mover caja**. Bloquean `POST /caja/cobrar`
y `POST /recibos/:id/anular`. No bloquean agenda, clínica, presupuestos ni la anulación de
un cargo: un olvido administrativo no debe frenar la atención. Esto confirma el límite
que dejó C-09, porque aceptar y anular un cargo no tocan caja.

Mecanismo: una sola función `_caja_operable(fecha)` del servicio, usada por las dos rutas.
Busca una caja abierta con fecha anterior y responde `409` con mensaje fijo. El frontend no
interpreta el texto: lee `operable` y `bloqueo` de `GET /caja` (D-17). Red de seguridad:
`uq_caja_una_abierta` hace imposible abrir la caja de hoy con otra abierta.

*Alternativa*: bloquear también turnos y clínica, lectura literal de "operar". Es más
estricto, pero una caja olvidada dejaría al consultorio sin agenda, y C-04 a C-09 deberían
cambiar.

### D-07 — Una caja por día, sin reapertura **[aprobada 2026-10-31]**

Cerrar es definitivo y se puede hacer a cualquier hora. Después de cerrar, cobrar el mismo
día responde `409` y el cobro se hace al día siguiente. El roadmap fija `fecha` única, y
reabrir contradice la inmutabilidad.

*Alternativa*: reapertura por admin con motivo. Resuelve el cobro tardío, pero suma un
estado, una ruta y una excepción al trigger.

### D-08 — Imputación del cobro: por presupuesto, parcial, sin sobrepago **[aprobada 2026-10-31]**

`POST /caja/cobrar` recibe `{presupuesto_id, monto, medio}`. El paciente se toma del
presupuesto, así no hay cruce de datos. El presupuesto debe estar `aceptado`.

**Pendiente** = `SUM(movimiento.monto) WHERE presupuesto_id = X`. El cargo suma, y los `pago`
y `ajuste` restan o reponen, porque todos llevan `presupuesto_id`. Queda derivado y
sin columna nueva. `monto > pendiente` da `422`, y sin pendiente da `409`.

Se admiten parciales, cada uno con su recibo. Un pago mixto son dos recibos. Hoy todo cargo
viene de un presupuesto (C-09, D-17), así que toda deuda es cobrable por esta vía. El saldo
a favor solo nace al anular un cargo con pagos, y se devuelve anulando recibos: así se
cierra lo que dejó abierto D-14 de C-09.

*Alternativa A*: cobro contra el saldo total, con imputación automática al más antiguo. Es
más cómoda para la secretaria, pero la imputación y su reversa suman lógica.
*Alternativa B*: solo cobro total, sin parciales. Más simple, y no sirve para un tratamiento
largo pagado en cuotas.

### D-09 — Cuándo pasa a `cobrado` **[aprobada 2026-10-31]**

`aceptado → cobrado` en la transacción del cobro que deja el pendiente exactamente en 0.
Anular un recibo de un presupuesto `cobrado` lo devuelve a `aceptado`. Así el estado
nunca contradice a los movimientos. Es una vuelta atrás en la máquina de estados, y no
genera otro cargo. `aceptado` significa "con pendiente o con cargo anulado".

Si se anula el cargo de un `cobrado`, el estado sigue igual con `cargo_anulado: true`,
como en C-09; no se toca esa ruta.

*Alternativa*: `cobrado` como estado final, sin reversa. Más simple, pero mostraría cobrado
un presupuesto con deuda.

### D-10 — Numeración sin huecos

Las secuencias de Postgres dejan huecos en cada rollback, así que no sirven. Se usa una
fila contador:

```sql
INSERT INTO recibo_contador (id, ultimo) VALUES (1, 1)
ON CONFLICT (id) DO UPDATE SET ultimo = recibo_contador.ultimo + 1
RETURNING ultimo
```

`recibo_contador` tiene `id SMALLINT` con `CHECK (id = 1)`. El lock de fila dura hasta el
`commit` y el rollback devuelve el número. Este `INSERT ... ON CONFLICT` no necesita
semilla, ni en la migración ni en `create_all`. El número se pide lo más tarde posible, ya
con las validaciones pasadas, y siempre en la transacción del cobro. Cualquier error
termina en el rollback completo de `a_http`, que también devuelve el número.

*Alternativa descartada*: `MAX(numero) + 1`. Necesita igualmente serializar, y falla justo
ante la concurrencia.

### D-11 — Concurrencia

Orden fijo de locks, siempre con `FOR UPDATE`:

| Operación | Orden |
|---|---|
| Cobrar | caja → presupuesto → contador |
| Anular recibo | caja → recibo → presupuesto |
| Cierre | caja |

Como todo empieza por la caja, no hay ciclos, y los cobros del día quedan en serie. Con el
volumen de un consultorio no es un problema. El contador no sobra: garantiza el número
aunque dos pedidos caigan en cajas de días distintos justo en la medianoche.

- **Primer cobro del día**: `INSERT ... ON CONFLICT DO NOTHING` **sin indicar índice**, para
  cubrir `fecha` y `uq_caja_una_abierta`, y luego `SELECT ... FOR UPDATE` por fecha. Si no
  aparece la fila, otra caja quedó abierta: `409`.
- **Cobrar vs. cierre**: tras el lock se revalida `estado`. Si ganó el cierre, `409`.
- **Sobrepago**: el pendiente se lee después del lock del presupuesto.
- **Misma clave en paralelo**: la lectura de la clave no toma locks, así que este orden no
  cambia. La segunda sesión relee la clave después del lock de la caja (D-25).
- **Anular un cargo en paralelo**: esa ruta no toma la caja. El resultado equivale a
  que el cobro ocurrió antes, y deja saldo a favor (D-08). Es aceptable y no toca C-09.

### D-12 — Cierre **[aprobada 2026-10-31]**

`POST /caja/cierre` recibe `{caja_id, total_contado, motivo_diferencia?}`. `caja_id` evita
cerrar otra caja que la que se ve en pantalla. Bajo `FOR UPDATE`, el servidor calcula
`total_sistema` como `SUM(movimiento_caja.monto)`, y `diferencia`. Con diferencia y sin
motivo responde `422`; la pantalla no hace aritmética de dinero: conserva el importe y
pide el motivo. Se cierra cualquier caja abierta: la de hoy o una pendiente.

Se mantienen las tres columnas de la KB, con **un solo total contado**. El desglose
por medio se muestra en `GET /caja` para ayudar a contar, sin guardarse aparte.

*Alternativa*: `total_contado` por medio en una tabla `cierre_medio`. Da más control
(el efectivo se cuenta, la transferencia se concilia), pero cambia el modelo de la KB.

### D-13 — Anulación de recibo **[aprobada 2026-10-31]**

`POST /recibos/:id/anular` (admin) recibe `{motivo}`. En una transacción, con el orden de
D-11:

1. Valida la caja operable y asegura la caja de hoy.
2. Toma el recibo y responde `409` si ya está anulado.
3. Crea un `ajuste` por `-pago.monto`, con `anula_a_id`, `recibo_id`, `presupuesto_id`,
   `motivo` y concepto fijo.
4. Crea un `movimiento_caja` negativo en la caja de **hoy**, con el medio original.
5. Marca el recibo, y si el presupuesto estaba `cobrado` lo vuelve a `aceptado`.

**Una caja cerrada nunca se toca.** Anular un recibo de un día cerrado reduce el total de la
caja de hoy, que representa la devolución real del dinero. La caja de hoy debe estar
operable: con caja pendiente o con la de hoy cerrada responde `409`. La ruta de C-09 sigue
respondiendo `409` para un `pago`.

Responde `200` con el recibo: la fila ya existe, a diferencia del `201` de C-09.

Consecuencia: una anulación urgente espera a que la secretaria cierre la caja pendiente, o
al día siguiente si la de hoy ya está cerrada.

*Alternativa*: permitir anular con caja de hoy cerrada dejando la reversión para la
próxima caja. Evita la espera, pero el dinero se mueve un día y el movimiento queda
desfasado.

### D-14 — Inmutabilidad por triggers

Como en C-09: DDL en el modelo con `event.listen(..., "after_create", ...)`, literales
repetidos en la migración, test de paridad, una sentencia por `execute` y sin `%` en el
texto (`DDL()` interpola con `%`). `TRUNCATE` y `DROP` no los disparan.

| Tabla | Regla del trigger |
|---|---|
| `movimiento_caja` | `BEFORE UPDATE OR DELETE`: siempre rechaza |
| `movimiento_caja` | `BEFORE INSERT`: rechaza si la caja está cerrada |
| `caja` | `BEFORE DELETE`: siempre. `BEFORE UPDATE`: rechaza si `OLD.estado = 'cerrada'` |
| `recibo` | `BEFORE DELETE`: siempre. `BEFORE UPDATE`: solo admite `anulado` de falso a verdadero, con sus tres campos, sin cambiar el resto |

El borrado de un recibo también abriría un hueco, por eso RN-CO-04 depende de este trigger.
`clave_idempotencia` entra en "el resto": es inmutable (D-25).

### D-15 — El `pago` nace con recibo **[aprobada 2026-10-31]**

Orden en la transacción: recibo → `pago` con `recibo_id` → movimiento de caja. El trigger
impide completar `recibo_id` después. Se agrega `ck_movimiento_pago_con_recibo`
(`tipo <> 'pago' OR recibo_id IS NOT NULL`) y `uq_movimiento_pago_recibo`: un `pago` sin
recibo es imposible también por SQL.

Costo: varios tests de C-09 insertan `pago` sin recibo o con `recibo_id=123`, y hay que
reescribirlos con un helper `crear_recibo`. Las dos pruebas del contrato transitorio
(`test_movimiento_recibo_inexistente_aceptado`, `recibo_fk == 0`) cambian de sentido. Eso
modifica el requirement "Contrato de escritura para caja".

*Alternativa*: solo la FK, sin CHECK. Toca menos tests, pero la garantía queda en el
servicio.

### D-16 — Permisos **[aprobada 2026-10-31]**

Matriz de `03`, leída de forma literal:

| Ruta | `secretaria` | `admin` | `odontologo` |
|---|---|---|---|
| `POST /caja/cobrar` | Sí | `403` | `403` |
| `POST /caja/cierre` | Sí | `403` | `403` |
| `POST /recibos/:id/anular` | `403` | Sí | `403` |
| `GET /caja`, `GET /recibos` | Sí | Sí | `403` |

Admin **no** cierra ni siquiera un día anterior. Es separación de funciones: quien cobra
no anula, y quien anula no cierra. Sin Bearer, `401`. Vía `require_role`, más el chequeo
de rol en el servicio, como en C-09. RN-AU no suma requisitos: no hay reautenticación
para anular.

Riesgo: sin una secretaria activa, una caja pendiente frena cobros hasta dar de alta otra.
El seed tiene una, así que no afecta a la demo.

*Alternativa*: permitir a admin cerrar solo una caja pendiente, como salida de emergencia.
Evita ese bloqueo, pero contradice la matriz y hay que actualizar `03`.

### D-17 — Lecturas agregadas

Solo las que la pantalla necesita:

- `GET /caja?fecha=` (opcional): `{fecha, hoy, operable, bloqueo, caja, desglose}`. `bloqueo`
  es `null | "caja_pendiente" | "caja_cerrada"`. Sin `fecha` y con caja pendiente, `caja` es
  la pendiente. `desglose` da el subtotal por medio. Una caja abierta no tiene `total_sistema`
  guardado: se calcula al vuelo.
- `GET /recibos?fecha=`: recibos de la caja de esa fecha, con `paciente_nombre` para la
  lista (no es dato clínico).
- `pendientes` en `GET /cuentas/:paciente_id`, con valor por defecto `[]`, compatible con
  `CuentaOut` y sus tests.

### D-18 — Sin egresos **[aprobada 2026-10-31]**

`CHANGES.md` no incluye egresos, aunque RN-CO-02 y `04` los nombran. Los únicos negativos
son reversiones de recibos, y por eso `movimiento_caja.recibo_id` es NOT NULL.

*Alternativa*: agregar `POST /caja/egresos` con motivo, que requiere `recibo_id` nulo y más
pantalla. Se puede sumar luego sin romper lo de este change.

### D-19 — Sin PDF: comprobante en pantalla **[aprobada 2026-10-31]**

`02` lista "PDF (recibos, liquidaciones)", pero `CHANGES.md`, US-031 y RN-CO-04 no piden PDF
para C-10, y el PDF de C-11 está en la lista de recorte. El comprobante es una vista con
número, paciente, importe, medio, fecha y la leyenda "Pago simulado, sin validez fiscal".

*Alternativa*: `GET /recibos/:id/pdf`, con una dependencia nueva. Puede sumarse en C-11.

### D-20 — Obra social: entrega a C-11

El cargo sigue siendo por el total, sin descontar cobertura. En v1.0 el paciente paga todo
lo que no se ajuste. Para C-11 queda:

- Un `ajuste` con `presupuesto_id` y sin `anula_a_id` ya reduce el pendiente de D-08. Si
  lo deja en 0, C-11 debe aplicar `cobrado`, reutilizando la función del servicio.
- El Flujo 5 registra el cobro de una liquidación "en caja como ingreso", sin recibo de
  paciente. Hoy `movimiento_caja.recibo_id` es NOT NULL: C-11 debe migrarlo, con una
  referencia a la liquidación, y pasar por `_caja_operable`.

El contrato completo está en `CHANGES.md`, sección C-11 ("Contrato recibido de C-10").

### D-21 — Contrato heredado de C-09

| # | Obligación | Resolución |
|---|---|---|
| 1 | FK e índice de `recibo_id` | D-01 |
| 2 | `pago` nace con `recibo_id` | D-15 |
| 3 | Cuándo pasa a `cobrado` | D-08, D-09 |
| 4 | `concepto` fijo sin PHI | `Recibo {numero}`, `Anulación del recibo {numero}` |
| 5 | Reutilizar repo de cuentas | D-22 |
| 6 | Anular `pago` por recibo | D-13; la ruta de C-09 sigue en `409` |
| 7 | Cargo por el total, sin OS | D-20 |
| 8 | `tarjeta` vs. `tarjeta_simulada` | D-03 |
| 9 | Bloqueo no alcanza a C-09 | D-06 |

### D-22 — Capas y reutilización

- `modelos/caja.py`: `Caja`, `Recibo`, `ReciboContador`, `MovimientoCaja`, `MEDIOS`.
- `repos/caja_repo.py`: asegurar, lock, caja pendiente, suma y desglose, crear movimiento.
- `repos/recibo_repo.py`: siguiente número, crear, lock, listar por fecha, `por_clave` (D-25).
- `repos/cuenta_repo.py`: suma `pendiente_de_presupuesto` y `pendientes_de_paciente`, y
  `pago_de_recibo`. Reutiliza `por_paciente`, `saldo` y `crear_movimiento`. `asegurar`
  no hace falta: si hay cargo, hay cuenta.
- `servicios/caja_servicio.py`: `cobrar`, `cerrar`, `anular_recibo`, `obtener_caja`,
  `listar_recibos`. Reutiliza `Actor`, `construir_actor`, errores y `a_http`.
- `api/caja.py` (`/caja`) y `api/recibos.py` (`/recibos`), rutas que nombra `02`. El servicio
  hace `flush` y el router `commit`. `api/cobros.py` no se toca.

Sin subclases de error (ver Context). Un `IntegrityError` de las redes de seguridad se
traduce a `409` con `begin_nested()`, como C-09.

### D-23 — Sin PHI

Mensajes fijos y sin logs de motivos. Motivos en el cuerpo. `concepto` y recibo sin datos
clínicos. El test `sin_phi` y `sin-consola` se extienden a estas rutas y a `features/caja`.

### D-24 — Frontend

- `features/caja`: `CajaPage` (estado, totales, desglose, recibos), `CierreForm`,
  `RecibosLista`, `CobroModal`, `ComprobanteRecibo`, `api.ts`, `tipos.ts`.
- `App.tsx`: botón Caja y página `caja` con `RequireRole` para `admin` y `secretaria`, con
  `lazy`, como `CuentaPage`.
- `CuentaPage`: suma `pendientes`, cobrar (secretaria) y anular recibo (admin, en `pago`
  no anulado, con `MotivoForm`). Para secretaria pide cuenta y caja con `Promise.all`; si
  falla la caja, muestra la cuenta y deja que el servidor decida.
- El importe se valida con regex como texto y nunca pasa a `number`. Sin aritmética de
  dinero en el cliente. `formatearMoneda` para mostrar.
- `fecha` llega como `YYYY-MM-DD`: se formatea cortando el texto. **`new Date("2026-10-31")`
  se interpreta en UTC y en Argentina mostraría el día anterior**.
- `CobroModal` maneja la clave de D-25: la crea al abrir, la reutiliza en reintentos y
  congela importe y medio tras un fallo sin respuesta.
- `styles/caja.css` solo con variables de `tokens.css`, y estados con tokens semánticos
  existentes y texto visible. Si hiciera falta un token nuevo, se sube la `Revision`.

### D-25 — Idempotencia del cobro **[aprobada 2026-10-31]**

Sin clave, reintentar un parcial tras un error de red puede duplicarlo: el servidor pudo
haber confirmado aunque la respuesta nunca llegó. El tope de sobrepago (D-08) no lo evita,
porque un parcial repetido suele entrar en el pendiente. Se recomienda lo siguiente.

**Clave en el cuerpo.** `POST /caja/cobrar` exige `clave_idempotencia`, un UUID v4 en
minúsculas generado por el cliente. Va en `CobroIn` y no en un header `Idempotency-Key`:
todo el input de la API pasa hoy por esquemas `extra='forbid'`, el único header que se lee
a mano es la firma del webhook, y así se valida con `Field(pattern=...)` y da `422` como
cualquier campo. Viaja en el cuerpo, no se loguea y ninguna respuesta la devuelve.

**Garantía en la DB.** La columna vive en `recibo`, no en Redis ni en una tabla aparte, para
que nazca y se revierta en la misma transacción que el cobro. No hay vencimiento ni purga:
dura lo que dura el recibo.

- `uq_recibo_clave_idempotencia`: `UNIQUE (clave_idempotencia)`, que además da el índice.
- `ck_recibo_clave_formato`: `clave_idempotencia ~
  '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'`, la misma regex del
  esquema. No contiene `%`, así que no choca con `DDL()` (D-14).
- El trigger de `recibo` la protege como al resto de las columnas.
- `NOT NULL` no necesita backfill porque la tabla es nueva. `crear_recibo` de los tests
  genera una clave, y C-12 debe hacer lo mismo si siembra recibos.

**Qué es "el mismo pedido".** Se compara `presupuesto_id`, `monto` y `medio`. `recibo` no
guarda `presupuesto_id`: sale del `pago` del recibo con `pago_de_recibo`, único por
`uq_movimiento_pago_recibo`. `monto` se compara como `Decimal`, así `400` y `400.00` son
iguales. `emitido_por` no se compara: otra secretaria reintentando recibe el recibo
original, que igual puede ver en `GET /recibos`.

**Orden dentro de `cobrar`.** El rol va primero, para que un reintento no saltee los
permisos:

1. Busca la clave con un `SELECT` sin lock. Si existe, resuelve como reintento y termina.
2. `_caja_operable`.
3. Asegura y toma la caja con `FOR UPDATE`.
4. **Relee la clave**. Si existe, resuelve como reintento.
5. Revalida el estado de la caja.
6. Toma el presupuesto y valida el cobro.
7. Pide el número (D-10) y crea recibo, `pago` y movimiento de caja (D-15).

El orden de locks de D-11 no cambia: ninguna lectura de la clave bloquea, y las dos ocurren
antes del contador, así que **un reintento nunca consume número**. Que el paso 4 preceda al
5 importa: si el cierre ocurrió mientras la segunda sesión esperaba, igual recibe el recibo
original y no un `409`.

**Dos pedidos con la misma clave a la vez.** Ambos pasan el paso 1 y se ordenan en la caja.
El segundo espera el `commit` del primero y su relectura lo ve: Postgres usa `READ COMMITTED`
y el repo no cambia el aislamiento, de modo que cada sentencia toma una foto nueva. Resultado:
un `201` y un `200`, con un solo recibo. Si el primero falla, el segundo no encuentra la clave
y cobra normalmente.

La UNIQUE queda como red de seguridad. Según el orden anterior no debería saltar, porque
dos cajas no conviven abiertas. Si salta, se traduce a `409` como en D-22, con rollback total,
y el número vuelve al contador. Un reintento posterior devuelve el original.

**Respuesta de un reintento.** `200` con el mismo cuerpo de `CobroOut`; `201` solo si se
creó el recibo. El servicio devuelve el recibo y si fue creado. En un reintento, el router
arma la respuesta y hace `rollback` en vez de `commit`: eso descarta una caja que el paso 3
pudiera haber creado en el cruce de medianoche, y el reintento no deja filas.

**Misma clave con otro contenido: `409`.** Se usa `ConflictoError` sin subclase, con mensaje
fijo, porque `a_http` hace `_STATUS[type(error)]` y una subclase daría `KeyError`. `409` y no
`422`: el pedido es válido por sí mismo y choca con algo ya registrado, que es lo que el mapeo
de `clinica_comun.py` llama duplicado; `422` significa en este change un dato a corregir
(sobrepago, diferencia sin motivo), y acá no hay nada que el usuario pueda corregir. No se
crean filas ni se consume número.

**Reintentos tardíos.** La clave se resuelve en los pasos 1 y 4, antes de cualquier control
de caja o presupuesto, porque repetir la respuesta no mueve dinero:

| Situación al reintentar | Respuesta |
|---|---|
| La caja del recibo ya se cerró | `200` con el recibo original; la caja no se toca |
| Hay una caja pendiente o la de hoy está cerrada | `200` con el recibo original; no se evalúa `_caja_operable` |
| El recibo fue anulado | `200` con `anulado: true`; no vuelve a cobrar ni a revertir |
| El presupuesto cambió de estado o se dio de baja | `200` con el recibo original |

Un recibo anulado no libera su clave. Para volver a cobrar se abre otro formulario, que
tiene clave nueva. La pantalla muestra el comprobante del recibo devuelto, con su estado.

Un cobro rechazado (`4xx`) o revertido no deja rastro, así que su clave sigue libre y se
evalúa de cero: no es un reintento.

**Frontend.** `CobroModal` genera la clave con `crypto.randomUUID()` al abrirse y la conserva
mientras siga abierto. `201` y `200` se muestran igual.

- Sin respuesta o con `5xx` el resultado es incierto: importe y medio se congelan, y la
  única salida es Reintentar, con la misma clave, o Cerrar, que refresca la cuenta para ver
  si el cobro entró.
- Con una respuesta `4xx` nada se guardó: los campos vuelven a editarse y la clave sirve.
- Abrir el formulario otra vez genera una clave nueva.

`crypto.randomUUID()` exige contexto seguro. `localhost` lo es, y el deploy es local; servir
la app por HTTP en una red interna obligaría a reemplazarlo.

**Efecto sobre decisiones aprobadas.** El reintento es una excepción acotada, no un cambio:

- D-08: el cuerpo suma un campo. La imputación no cambia.
- D-06 y D-07: un reintento responde `200` con caja bloqueada o cerrada. Es coherente con
  D-06, porque "operar" significa mover caja y un reintento no la mueve.
- D-10, D-11 y D-15: no cambian.

*Alternativa A*: mismo mecanismo con el header estándar `Idempotency-Key`. La columna, la
UNIQUE y el orden de la transacción son iguales. Es más reconocible, pero `CobroIn` no lo
valida, y hay que leerlo aparte en el router y pasarlo por `fetchConAuth`.
*Alternativa B*: sin clave, como estaba. Se mantienen el botón deshabilitado y el tope de
sobrepago, y un duplicado se corrige anulando el recibo. No agrega columna ni tareas, pero
un reintento puede emitir un recibo de más y la anulación exige caja operable y a un admin.

## UI Mockups

- Design system revision: 1
- Decision: no (project policy)
- Date: 2026-10-31
- Approval del sistema: approved (2026-10-28, by user)

Las tareas de frontend usan `design-system/tokens.css`. No hay mockups por change
(`Mode: system-only`, coincide en `.active-orchestrator-state.json` y `README.md`).

## Diferencias entre KB, `CHANGES.md`, specs y código

| # | Diferencia | Resolución |
|---|---|---|
| 1 | `04`: medio `tarjeta`; regla dura: `tarjeta_simulada` | D-03; `04` corregido |
| 2 | `04`: `Caja 1──1 CierreDiario`; roadmap: el cierre son columnas de `Caja` | Se sigue el roadmap; `04` corregido |
| 3 | `04`: `Recibo` sin autor ni datos de anulación | Se agregan por RN-GL-02; `04` actualizado |
| 4 | RN-CO-02 y `04` hablan de egresos; `CHANGES.md` no | D-18; RN-CO-02 aclarada en `05`, `04` mantiene la mención |
| 5 | `02` lista PDF de recibos; C-10 no | D-19 |
| 6 | `08`: "cierres" en el cron; RN-CO-01 exige un cierre con conteo | Sin cierre automático; aclarar `08` |
| 7 | Flujo 5 ingresa a caja sin recibo; `MovimientoCaja` tiene `recibo_id` | D-20; contrato en la sección C-11 de `CHANGES.md` |
| 8 | RN-CO-01 dice "operar" sin definir el alcance | D-06; `05` aclarado |
| 9 | Spec C-09 admitía `pago` con recibo inexistente | Era transitorio; D-15 lo reemplaza |
| 10 | `api/cobros.py` dice "caja real en C-09/C-10"; `02` usa `/caja` y `/recibos` | Rutas de `02`; stub intacto |
| 11 | Matriz sin ruta de apertura de caja | D-05 |

## Risks / Trade-offs

- [Contador como cuello de botella] → Un solo consultorio; la caja ya serializa los cobros.
- [Número consumido fuera de transacción] → Siempre en la transacción del cobro; test con
  rollback forzado y test concurrente de 20 sesiones.
- [Doble clic o reintento tras error de red] → Mitigado por D-25: la clave con UNIQUE
  evita duplicar el cobro, y el botón sigue deshabilitado al enviar.
- [Clave perdida al recargar la página] → Si se recarga tras un fallo sin respuesta, la clave
  se pierde porque vive en el formulario. La cuenta refrescada muestra si el cobro entró;
  un cobro repetido a sabiendas se corrige anulando el recibo.
- [Olvidar el cierre frena cobros] → Banner con la fecha pendiente; se resuelve en la
  misma pantalla.
- [Anulación demorada por caja cerrada] → D-13, aceptado.
- [Cambio de `movimiento` rompe tests de C-09] → Se ajustan en la misma tarea que la
  migración y el modelo.
- [Triggers ausentes en tests] → DDL `after_create` y test de paridad con la migración.
- [`freezegun` no llega a `now()` de la DB] → Aserciones sobre `caja.fecha` y fechas
  calculadas en Python.
- [Corte de día en mitad de un pedido] → `hoy_operativo()` se calcula una sola vez por
  pedido.
- [Admin sin acceso de cierre] → D-16.

## Migration Plan

1. `alembic upgrade head` aplica 007. Agrega tablas y restricciones sobre `movimiento`.
2. Reversión: `alembic downgrade 006_presupuestos_cc`. Datos ficticios.
3. Sin seed nuevo: C-12 siembra la demo. El contador se crea con el primer recibo.
