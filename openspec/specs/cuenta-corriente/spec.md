# cuenta-corriente Specification

## Purpose
Dar a la secretaria y al admin la deuda de cada paciente a partir de movimientos
inmutables, con saldo siempre derivado y anulación por contramovimiento (US-030;
RN-CO-02, RN-CO-03), y dejar el contrato de escritura que usa caja en C-10.

## Requirements

### Requirement: Una cuenta corriente por paciente

El sistema SHALL mantener como máximo una cuenta por paciente, creada al generarse el
primer movimiento. Consultar SHALL NOT crear filas.

#### Scenario: Primer cargo crea la cuenta

- **WHEN** se acepta el primer presupuesto de un paciente
- **THEN** existe una cuenta para ese paciente con un movimiento

#### Scenario: Segundo cargo reutiliza la cuenta

- **WHEN** se acepta un segundo presupuesto del mismo paciente
- **THEN** sigue habiendo una sola cuenta, con dos movimientos

#### Scenario: Primer cargo concurrente

- **WHEN** dos presupuestos distintos de un paciente sin cuenta se aceptan a la vez
- **THEN** ambos responden `200` y existe una sola cuenta con dos cargos

#### Scenario: Paciente duplicado

- **WHEN** se inserta directamente una segunda cuenta para el mismo paciente
- **THEN** la DB la rechaza por UNIQUE

### Requirement: Saldo derivado de los movimientos

El saldo SHALL calcularse como la suma de todos los movimientos de la cuenta. Un saldo
positivo SHALL significar deuda del paciente. No SHALL existir columna de saldo ni
operación que lo escriba.

#### Scenario: Suma de cargos, pagos y ajustes

- **WHEN** la cuenta tiene un cargo de 1000.00, un pago de -400.00 y un ajuste de -100.00
- **THEN** `GET /cuentas/:paciente_id` devuelve `saldo` `"500.00"`

#### Scenario: Saldo a favor

- **WHEN** los pagos superan a los cargos
- **THEN** `saldo` es negativo

#### Scenario: Sin columna de saldo

- **WHEN** se inspecciona la tabla `cuenta_corriente`
- **THEN** no tiene columna `saldo`

#### Scenario: El saldo no se envía

- **WHEN** se hace `PUT` o `PATCH` sobre `/cuentas/:paciente_id`
- **THEN** responde `405`

### Requirement: Consulta de la cuenta

`GET /cuentas/:paciente_id` SHALL devolver `paciente_id`, `saldo` y los movimientos del
más reciente al más antiguo, con `tipo`, `monto`, `concepto`, referencias, `motivo`,
`created_at` y `anulado`.

#### Scenario: Paciente sin cuenta

- **WHEN** se consulta un paciente existente sin movimientos
- **THEN** responde `200` con `saldo` `"0.00"` y lista vacía, sin crear filas

#### Scenario: Paciente inexistente

- **WHEN** el paciente no existe
- **THEN** responde `404`

#### Scenario: Paciente dado de baja con movimientos

- **WHEN** se consulta un paciente eliminado que tiene movimientos
- **THEN** responde `200`, porque la deuda se conserva

#### Scenario: Cargo anulado

- **WHEN** un cargo tiene contramovimiento
- **THEN** el cargo se lista con `anulado: true` y el contramovimiento con `anula_a_id`

### Requirement: Signo del monto según el tipo

Los tipos SHALL ser `cargo`, `pago` y `ajuste`. `cargo` SHALL ser positivo, `pago`
negativo y `ajuste` distinto de cero, en montos con dos decimales.

#### Scenario: Monto cero

- **WHEN** se inserta directamente un movimiento con `monto` 0
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Cargo negativo

- **WHEN** se inserta directamente un `cargo` con monto negativo
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Pago positivo

- **WHEN** se inserta directamente un `pago` con monto positivo
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Tipo fuera del catálogo

- **WHEN** se inserta directamente un `tipo` desconocido
- **THEN** la DB lo rechaza por CHECK

### Requirement: Movimientos inmutables

Un movimiento SHALL NOT poder modificarse ni borrarse, tampoco por SQL directo. La
autoría y la fecha SHALL quedar registradas en cada fila (RN-GL-02).

#### Scenario: UPDATE directo

- **WHEN** se ejecuta `UPDATE` sobre una fila de `movimiento`
- **THEN** la DB lo rechaza

#### Scenario: DELETE directo

- **WHEN** se ejecuta `DELETE` sobre una fila de `movimiento`
- **THEN** la DB lo rechaza

#### Scenario: Sin escritura directa por API

- **WHEN** se hace `POST /cuentas/:paciente_id/movimientos`
- **THEN** responde `404`, porque esa ruta no existe

#### Scenario: Autoría del cargo

- **WHEN** se genera un cargo al aceptar
- **THEN** el movimiento guarda `creado_por` con el usuario que aceptó

### Requirement: Anulación por contramovimiento

`POST /cuentas/:paciente_id/movimientos/:id/anular` SHALL exigir `motivo` y crear un
`ajuste` por el monto opuesto con `anula_a_id`, sin tocar la fila original. Solo un
`cargo` SHALL poder anularse por este endpoint, y una sola vez.

#### Scenario: Anulación de un cargo

- **WHEN** un admin anula un cargo de 1000.00 con `motivo`
- **THEN** responde `201` con un `ajuste` de -1000.00, y el saldo baja 1000.00

#### Scenario: Sin motivo

- **WHEN** se anula sin `motivo`
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Doble anulación

- **WHEN** se anula otra vez el mismo cargo
- **THEN** responde `409`

#### Scenario: Doble anulación concurrente

- **WHEN** dos sesiones anulan el mismo cargo a la vez
- **THEN** una responde `201`, la otra `409` y existe un solo contramovimiento

#### Scenario: Anular un contramovimiento

- **WHEN** se intenta anular un `ajuste`
- **THEN** responde `409`

#### Scenario: Anular un pago

- **WHEN** se intenta anular un `pago`
- **THEN** responde `409`, porque un pago se anula desde su recibo en C-10

#### Scenario: Movimiento de otra cuenta

- **WHEN** el movimiento no pertenece a la cuenta de `paciente_id`
- **THEN** responde `404`

#### Scenario: La base de datos exige motivo

- **WHEN** se inserta directamente un movimiento con `anula_a_id` y sin `motivo`
- **THEN** la DB lo rechaza por CHECK

### Requirement: Presupuesto con cargo anulado

Anular el cargo de un presupuesto SHALL conservar su estado `aceptado` y SHALL
reflejarse en el campo derivado `cargo_anulado` de sus respuestas.

#### Scenario: Estado conservado

- **WHEN** se anula el cargo de un presupuesto `aceptado`
- **THEN** el presupuesto sigue `aceptado` con `cargo_anulado: true`

#### Scenario: Los hallazgos pueden presupuestarse de nuevo

- **WHEN** se crea otro presupuesto sobre los mismos hallazgos activos
- **THEN** se acepta como un presupuesto nuevo con su propio cargo

### Requirement: Permisos sobre la cuenta corriente

`secretaria` y `admin` SHALL leer cualquier cuenta. Solo `admin` SHALL anular. El rol
`odontologo` SHALL NOT acceder a `/cuentas`. Sin Bearer válido SHALL responder `401`.

#### Scenario: Secretaria lee

- **WHEN** una secretaria hace `GET /cuentas/:paciente_id`
- **THEN** responde `200`

#### Scenario: Secretaria no anula

- **WHEN** una secretaria intenta anular un cargo
- **THEN** responde `403` y nada cambia

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo consulta `/cuentas/:paciente_id`
- **THEN** responde `403`

#### Scenario: Sin autenticación

- **WHEN** se llama a `/cuentas` sin Bearer
- **THEN** responde `401`

### Requirement: Sin datos clínicos en la cuenta

Los movimientos generados por el sistema SHALL usar un `concepto` fijo, sin piezas,
hallazgos ni tratamientos. Los motivos SHALL NOT escribirse en logs.

#### Scenario: Concepto del cargo

- **WHEN** se genera el cargo del presupuesto 12
- **THEN** `concepto` es `Presupuesto 12`

#### Scenario: Motivo fuera de los logs

- **WHEN** se anula un cargo con un texto marcador en `motivo`
- **THEN** ningún registro de log capturado contiene ese texto

#### Scenario: Frontend sin consola

- **WHEN** se revisa el código de `features/cuenta-corriente`
- **THEN** no contiene llamadas a `console`

### Requirement: Contrato de escritura para caja

El esquema SHALL admitir movimientos `pago` con `recibo_id`, y `recibo_id` SHALL ser
nulo sin restricción de clave foránea hasta que exista la tabla de recibos. Este
change SHALL NOT exponer ninguna operación de cobro.

#### Scenario: Pago cargado directamente

- **WHEN** se inserta directamente un `pago` con `recibo_id` sin recibo existente
- **THEN** la DB lo acepta y el saldo lo refleja

#### Scenario: Sin cobro por API

- **WHEN** se buscan las rutas de la aplicación
- **THEN** no existe ninguna que registre un `pago` ni que marque `cobrado`

### Requirement: Pantalla de cuenta corriente

`features/cuenta-corriente` SHALL mostrar con texto si el paciente debe, no debe o
tiene saldo a favor, y sus movimientos. Se SHALL acceder desde la agenda para
`secretaria` y `admin`, y solo `admin` SHALL ver la acción de anular.

#### Scenario: Secretaria ve la deuda

- **WHEN** una secretaria abre la cuenta desde un turno
- **THEN** ve el saldo, y cargos y anulaciones sin acción de anular

#### Scenario: Sin movimientos

- **WHEN** el paciente no tiene movimientos
- **THEN** la pantalla dice que no tiene movimientos

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo ve un turno en la agenda
- **THEN** no tiene acceso a la cuenta corriente

#### Scenario: Admin anula con motivo

- **WHEN** un admin anula un cargo sin escribir motivo
- **THEN** el formulario no se envía e indica que el motivo es obligatorio

#### Scenario: Acceso al presupuesto

- **WHEN** un cargo tiene `presupuesto_id`
- **THEN** se puede abrir ese presupuesto en modo lectura
