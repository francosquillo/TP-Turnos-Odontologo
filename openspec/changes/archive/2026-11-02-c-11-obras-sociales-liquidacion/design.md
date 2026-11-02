# Design — c-11-obras-sociales-liquidacion

## Context

Ver `proposal.md` (Why). Estado verificado en el código el 2026-11-01:

- La cabeza de Alembic es `007_caja_recibos`. Tres tests la fijan (`test_c08_migracion`,
  `test_c09_migracion`, `test_c10_migracion`), y `test_c05_reserva_pg.py` lista las migraciones.
- **No existe la prestación.** `turno` no tiene tratamiento, e `item_presupuesto` no tiene
  turno ni fecha de ejecución. El único registro de un tratamiento acordado es el ítem de
  presupuesto. La fecha más cercana es `presupuesto.decidido_at`.
- **`/pacientes` es un stub.** No hay CRUD ni pantalla de pacientes. El frontend llega al
  paciente desde la agenda. `paciente` tiene `cobertura_os` en texto libre, no las FK que
  dice `04`.
- `tratamiento.codigo_nomenclador` existe, pero el seed no lo completa.
- `/os` es un stub de C-01 con un comentario desactualizado. `test_routers.py` exige ese prefijo.
- **No hay función reutilizable para `cobrado`**: es un `actualizar` dentro de `cobrar()`.
  Además, `caja_servicio` importa `presupuesto_servicio`, así que `aceptar` no puede importar
  `caja_servicio` sin un ciclo.
- `_caja_operable` es privada. No hay librería de PDF en `requirements.txt`: C-10 no generó PDF
  (D-19).
- `movimiento` y `movimiento_caja` son inmutables por trigger. Ningún flujo crea hoy un
  `ajuste` sin `anula_a_id`.
- `a_http` busca el tipo exacto del error: no se crean subclases. `MetodoHttp` no incluye
  `DELETE`. La SPA navega con el estado `pagina` de `App.tsx`.
- Los tests usan `create_all`: el DDL debe estar en los modelos además de en la migración.

## Goals / Non-Goals

**Goals:** cumplir US-040, US-041, RN-OS-01..03, Flujo 5 y el contrato de C-10, con el diseño
más simple que evite cobrar dos veces lo mismo. Sin plan, nada cambia.

**Non-Goals:** débitos o cobros parciales de la OS; ABM de nomenclador en pantalla; importación
de nomenclador; CRUD de pacientes; registrar la ejecución real del tratamiento; worker para
exportar; multi-sede, AFIP y pagos reales.

## Decisions

Las marcadas **[a confirmar]** son decisiones no obvias. Governance MEDIO: confirmar antes de
aplicar.

### D-01 — Migración `008_obras_sociales`

Encadenada a `007_caja_recibos`, una sola. Crea `obra_social`, `plan`, `arancel`, `liquidacion`
e `item_liquidacion`. Altera `paciente`, `presupuesto`, `item_presupuesto`, `movimiento` y
`movimiento_caja`. Repite los literales de los modelos, y un test los compara, como en C-10.
`ALTER TABLE` no dispara triggers de fila.

El downgrade falla si hay ingresos de liquidación, porque `recibo_id` no puede volver a
`NOT NULL` y `movimiento_caja` es inmutable. Se prefiere el error a perder datos, como en 007.

### D-02 — Prestación = ítem de presupuesto aceptado **[a confirmar]**

La prestación liquidable es un `item_presupuesto` de un presupuesto `aceptado` o `cobrado`, y su
fecha es el día operativo de `decidido_at`. `item_liquidacion` referencia
`item_presupuesto_id`, sin `turno_id`.

Esto liquida lo acordado, no lo ejecutado: es una simplificación real. Un tratamiento aceptado
y nunca realizado se liquidaría igual. Es aceptable con datos ficticios, y queda documentado.

*Alternativa*: vincular ítems a turnos asistidos. Es más fiel a `04` (`Turno 0—1
ItemLiquidacion`), pero exige un flujo clínico nuevo y pantalla en agenda. No entra en el plazo.

### D-03 — Congelar la cobertura al aceptar **[a confirmar]**

`aceptar` guarda `presupuesto.plan_id`, `item_presupuesto.arancel_id` e
`item_presupuesto.cubierto`, todos nulables, y resuelve el arancel de la fecha de aceptación.
Liquidar solo copia esos valores. Sigue el patrón del precio congelado de C-09.

Como aceptación y prestación son el mismo día (D-02), esto cumple RN-OS-03. Lo que paga el
paciente y lo que se presenta a la OS salen del mismo número y no pueden divergir. Tampoco
afecta un cambio posterior de plan o de arancel.

*Alternativa*: resolver todo al liquidar, sin columnas nuevas. Es menos DDL, pero un arancel
retroactivo cobraría a la OS lo que el paciente ya pagó.

### D-04 — Regla de cobertura

`arancel.precio` es lo que la OS paga por el código y el plan. `04` no define un porcentaje:
se deriva. Función pura única, usada por el validador y por `aceptar`:

```
cubierto = min(arancel, precio) × cantidad    a_cargo = precio × cantidad − cubierto
```

El tope evita que la cobertura supere el cargo. La liquidación usa `cubierto`, no el arancel
bruto. El validador usa `precio_base`, y `aceptar` usa el precio del ítem: pueden diferir
legítimamente si cambió el catálogo.

### D-05 — Cuándo se aplica: al aceptar **[a confirmar]**

Con cobertura mayor a cero, `aceptar` crea el `ajuste` negativo en el mismo savepoint del cargo.
Concepto fijo `Cobertura obra social`, sin `recibo_id` ni `anula_a_id`. Si el pendiente queda en
0, el presupuesto pasa a `cobrado`. El cargo sigue siendo por el total, como pide el contrato.

Es la forma más simple de cumplir RN-OS-01 ("antes del cobro"): no hay paso que olvidar, ni
pantalla nueva, ni estado en que el paciente pagó todo y la OS también. Sin plan, `aceptar` es
idéntico a hoy y los tests de C-09 y C-10 no cambian. Como no toca caja, RN-CO-01 no lo bloquea.

Red de seguridad: `uq_movimiento_cobertura_presupuesto`, índice único parcial sobre
`presupuesto_id` donde `tipo = 'ajuste' AND anula_a_id IS NULL AND recibo_id IS NULL AND
monto < 0`.

Esto cambia dos textos de specs: "`cobrado` solo por caja y recibos" y "ninguna ruta de
`/presupuestos` marca `cobrado`". El propio contrato de C-10 lo exige si el `ajuste` deja el
pendiente en 0.

*Alternativa*: un botón "aplicar cobertura" de la secretaria. Más explícito, pero suma ruta,
pantalla y una ventana en la que se puede cobrar sin cobertura.

### D-06 — Anular un cargo con cobertura

`anular_cargo` crea además el contramovimiento positivo del `ajuste` de cobertura, con
`anula_a_id` y el mismo motivo. Sin esto, anular dejaría un saldo a favor falso igual a la
cobertura. Si un ítem está en cualquier liquidación, responde `409`: el `borrador` se descarta
primero (D-10), y una presentada ya salió hacia la OS.

La ruta sigue sin anular un `ajuste` suelto.

### D-07 — Plan del paciente **[a confirmar]**

Se agrega `paciente.plan_id` (FK RESTRICT, nulable, con índice). La OS se deriva del plan, para
no repetir `obra_social_id` (3NF), y `04` se corrige. `cobertura_os` queda como está, sin uso
nuevo: quitarla obligaría a tocar C-02 sin beneficio.

Como no hay CRUD de pacientes, se suma solo `PUT /pacientes/:id/plan` en el router stub. El
stub `GET` queda.

### D-08 — Aranceles versionados

`EXCLUDE USING gist (plan_id WITH =, codigo_nomenclador WITH =, daterange(vigencia_desde,
vigencia_hasta, '[]') WITH &&)`, con `btree_gist` de C-01. `vigencia_hasta` nulo es abierto.
Precio mayor a cero por CHECK.

`POST /aranceles` crea, y `PATCH /aranceles/:id` admite solo `vigencia_hasta`: `extra='forbid'`
rechaza `precio`. Una versión nueva son dos pasos: cerrar y crear. No hay cierre automático. La
auditoría de RN-GL-02 vive en la fila (`creado_por`, `created_at`, `cerrado_por`, `cerrado_at`),
según el patrón del repo. Sin DELETE.

### D-09 — Generación de la liquidación

`liquidacion`: `os_id`, `periodo` (DATE con día 1 por CHECK), `estado`, `total NUMERIC(16,2)`,
`creada_por` y los pares de autor y fecha de presentar y cobrar, más `cobro_revertido_at` y
`cobro_revertido_por`.

`item_liquidacion`: `liquidacion_id`, `item_presupuesto_id` (**UNIQUE**), `plan_id`, `arancel_id`
nulable, `fecha_prestacion`, `monto`. `revision` es derivado de `arancel_id IS NULL` y un CHECK
exige monto 0 en ese caso.

Selección: presupuesto `aceptado` o `cobrado`, con `plan_id` de esa OS, `decidido_at` dentro del
mes en `America/Argentina/Buenos_Aires`, cargo sin anular y sin fila previa. Sin filas: `409`.

**Sin unicidad por OS y período.** La unicidad por prestación ya impide cobrar dos veces, y deja
facturar lo que apareció tras presentar. La colisión concurrente cae en el UNIQUE y responde
`409`, sin locks.

### D-10 — Descartar borrador con borrado físico **[a confirmar]**

`POST /liquidaciones/:id/descartar` borra el `borrador` y sus filas. Es una excepción a la letra
de RN-GL-01, justificada porque un borrador no tiene efecto financiero, no salió del sistema y
se recrea idéntico. Es `POST` porque `MetodoHttp` no tiene `DELETE`.

*Alternativa*: `deleted_at`, con UNIQUE parcial sobre las filas vigentes. Respeta la letra, a
cambio de más DDL y filtros.

### D-11 — Revisión manual **[a confirmar]**

Una prestación sin arancel al aceptar ya la pagó completa el paciente. Por eso no se vuelve
liquidable: un arancel retroactivo cobraría dos veces. La fila aparece con `revision: true` y
monto 0, no bloquea `presentar`, y en el informe se lista como no liquidada. La resolución real
(reclamar a la OS y devolver al paciente) queda fuera del sistema en v1.0.

*Alternativa*: bloquear `presentar` hasta resolverlas. Sin vía de resolución, la liquidación
quedaría trabada para siempre.

### D-12 — Cobro: contrato de C-10

`POST /liquidaciones/:id/cobrar {medio}`. Solo `admin`. Sin `POST /caja/cobrar`, sin recibo.

1. `hoy_operativo()`.
2. Control de caja y apertura implícita, con `abierta_por` igual al autor.
3. `FOR UPDATE` sobre la liquidación: orden caja → liquidación.
4. Exige `presentada`, sin reversión y con total mayor a 0; si no, `409`.
5. Inserta `movimiento_caja` con `liquidacion_id`, y pasa a `cobrada` en la misma transacción.

No usa `clave_idempotencia`: el estado, con la fila bloqueada, cumple ese papel (`CHANGES.md`).
Los índices únicos cubren lo demás. Una `IntegrityError` responde `409`.

Se suma en `caja_servicio` una función pública
`caja_para_movimiento(repos, hoy, usuario_id) -> Caja`, que llama a `_caja_operable` y a
`_asegurar_y_bloquear`. Así no se copia ni se importa un nombre privado. `cobrar` y
`anular_recibo` no cambian.

Admin registra el ingreso porque el actor del Flujo 5 es admin y la matriz le da Liquidaciones.
Eso **no habilita `/caja`**: D-16 de C-10 sigue igual, y hay un test que lo prueba.

### D-13 — Reversión **[a confirmar]**

`POST /liquidaciones/:id/revertir-cobro {motivo}`. Mismo orden de locks, movimiento negativo en
la caja de hoy con el medio original y `motivo`, como D-13 de C-10. Vuelve a `presentada` con
`cobro_revertido_at`.

Como el contrato permite un solo ingreso por liquidación, **una liquidación revertida no se
puede volver a cobrar**. Sus prestaciones quedan tomadas por el UNIQUE. Es un caso de error
excepcional, y se acepta para no debilitar la garantía.

*Alternativa*: permitir recobrar, con índices por ciclo. Agrega complejidad para un caso que la
demo no necesita.

### D-14 — `movimiento_caja`

`recibo_id` nulable; `liquidacion_id` con FK RESTRICT e índice `ix_movcaja_liquidacion_id`;
`ck_movcaja_una_referencia` con `num_nonnulls(recibo_id, liquidacion_id) = 1`;
`uq_movcaja_liq_ingreso` y `uq_movcaja_liq_reversion`, parciales por signo. `uq_movcaja_ingreso` y
`uq_movcaja_reversion` no cambian: los `NULL` no chocan. `ck_movcaja_medio` y el resto siguen
igual.

### D-15 — Ingresos en Caja

`EstadoCajaOut` suma `ingresos_liquidacion` con `liquidacion_id`, `obra_social`, `periodo`,
`medio`, `monto` con signo y `created_at`. Sin datos de pacientes, porque la secretaria los ve.
La pantalla los lista aparte de los recibos. `GET /recibos` no cambia. Con esto, el cierre se
puede explicar.

### D-16 — Permisos

| Ruta | `admin` | `secretaria` | `odontologo` |
|---|---|---|---|
| Escritura de `/obras-sociales`, `/planes`, `/aranceles` | Sí | `403` | `403` |
| Lectura de esas rutas | Sí | Sí | Sí |
| `PUT /pacientes/:id/plan`, `GET /validador-cobertura` | Sí | Sí | `403` |
| `GET /liquidaciones`, `GET /liquidaciones/:id` | Sí | `403` | Solo sus filas |
| Resto de `/liquidaciones` y exportar | Sí | `403` | `403` |

La matriz dice "Ver" para odontólogo, sin más. Se limita a las filas de sus presupuestos, como
el resto de la clínica: las filas tienen nombre de paciente. **[a confirmar]** Validador: US-040
nombra a la secretaria, y se suma admin porque también ve la cuenta.

### D-17 — Exportación sincrónica

**Sin worker.** Una liquidación son decenas o cientos de filas de una OS y un mes: se genera en
menos de un segundo. El worker agregaría job, estado, descarga diferida y blob fuera de Redis
para un problema que no existe.

- **CSV**: `csv` de la biblioteca estándar, con `;` y BOM UTF-8 para Excel en español. Celdas que
  empiezan con `= + - @` llevan `'` adelante (inyección de fórmulas).
- **PDF**: `reportlab` Platypus, con Helvetica y sin sub ni superíndices unicode. Se ejecuta con
  `asyncio.to_thread` porque es CPU bloqueante en una ruta async. Dependencia nueva, con versión
  fija, verificada al instalar. **Obliga a reconstruir las imágenes.**

Ambos se arman en `servicios/liquidacion_export.py` como funciones puras, desde un mismo modelo
de filas agrupadas por plan. Incluyen la leyenda "Datos ficticios, sin validez fiscal".

### D-18 — Rutas

`/obras-sociales` reemplaza el stub `/os`, conforme a `02`, y `test_routers.py` se actualiza.
Rutas planas, como en `CHANGES.md`: `/planes?os_id=`, `/aranceles?plan_id=`. Nuevos:
`api/liquidaciones.py` y `api/validador_cobertura.py`, con prefijo propio.

### D-19 — Capas y reutilización

- `servicios/cobertura_servicio.py`: regla pura (D-04), resolución de arancel y aplicación. No
  importa otros servicios, y así rompe el ciclo.
- `presupuesto_servicio.saldar_si_corresponde(...)`: extrae el paso a `cobrado` de `cobrar()`.
  Lo usan `cobrar` y `aceptar`. Es la "función de `caja_servicio`" del contrato, que no existía y
  no podía vivir ahí.
- `servicios/obra_social_servicio.py`, `servicios/liquidacion_servicio.py`,
  `repos/obra_social_repo.py`, `repos/liquidacion_repo.py`.
- Reutiliza `Actor`, los errores de `clinica_servicio`, `Dinero`, `Motivo` y `MedioPago`. Sin
  subclases de error. El servicio hace `flush`, el router hace `commit`.

### D-20 — Frontend

- `features/liquidaciones`: lista, generar, detalle por plan, acciones. Descarga con
  `fetchConAuth` y `Blob`.
- `features/cuenta-corriente`: `PanelCobertura`, para `secretaria` y `admin`: plan y validador,
  sobre `GET /tratamientos`.
- `features/caja`: lista de ingresos.
- `App.tsx`: página `liquidaciones`. Sin ABM del catálogo: API y seed.
- Mismo patrón de `api.ts` con guardas de tipo, importes como texto y sin consola.

### D-21 — Seed

`OS Ficticia Demo`, con `Plan Base` y `Plan Plus`, cubriendo cinco de los seis tratamientos.
`EXT-001` queda sin arancel para mostrar la revisión. Un arancel con versión anterior cerrada
muestra RN-OS-03. Plan Plus cubre `PRO-001` al 100 % para mostrar `cobrado` sin recibo. Rellena
`codigo_nomenclador` solo si es `NULL`. Idempotente por clave natural.

## Risks / Trade-offs

- **Plazo (08/11, equipo de 3)** → grupos independientes y recortes marcados en `tasks.md`.
- **Liquidar lo acordado y no lo ejecutado (D-02)** → límite documentado, a declarar en la
  defensa.
- **`aceptar` y `anular_cargo` son rutas críticas de C-09** → la rama sin plan no cambia, y la
  suite de C-09 y C-10 corre sin modificaciones de comportamiento.
- **Carrera entre `anular_cargo` y generar** → la generación no bloquea el presupuesto, y un
  cargo anulado en ese instante podría entrar. Es improbable: un solo admin hace ambas cosas. Se
  acepta, y la liquidación puede descartarse.
- **Reconstruir imágenes por `reportlab`** → hay que avisar al equipo. Recortar el PDF lo evita.
- **Presupuestos ya aceptados** no tienen plan y no se liquidan. Sin migración de datos: son
  ficticios.

## Migration Plan

`alembic upgrade head` con `docker compose build` previo por `reportlab`, y seed después. El
downgrade solo funciona sin ingresos de liquidación (D-01).

## Open Questions

Ninguna bloquea técnicamente. Las decisiones **[a confirmar]** (D-02, D-03, D-05, D-07, D-10,
D-11, D-13, D-16) cambian lo que se construye: `tasks.md` las asume con la recomendación del
diseño, y deben confirmarse antes de `/opsx:apply`.
