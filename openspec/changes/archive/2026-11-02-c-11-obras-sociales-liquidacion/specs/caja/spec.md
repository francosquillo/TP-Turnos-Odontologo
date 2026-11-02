# Delta — caja

## ADDED Requirements

### Requirement: Ingreso de liquidación sin recibo

Un movimiento de caja SHALL referenciar exactamente uno de `recibo_id` o `liquidacion_id`, y la
base de datos SHALL garantizarlo. Cada liquidación SHALL tener como máximo un ingreso y una
reversión. `medio` SHALL seguir siendo obligatorio y del catálogo cerrado. El ingreso SHALL
pasar por el mismo control de caja que el cobro y la anulación: usa el día operativo del
servidor, abre la caja de hoy si falta y bloquea primero la caja y después la liquidación. El
`total_sistema` y el `desglose` SHALL incluirlo.

#### Scenario: Sin referencia

- **WHEN** se inserta directamente un movimiento de caja sin `recibo_id` ni `liquidacion_id`
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Con las dos referencias

- **WHEN** se inserta directamente un movimiento con `recibo_id` y `liquidacion_id`
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Segundo ingreso

- **WHEN** se inserta directamente otro ingreso de la misma liquidación
- **THEN** la DB lo rechaza por índice único parcial

#### Scenario: Segunda reversión

- **WHEN** se inserta directamente otra reversión de la misma liquidación
- **THEN** la DB lo rechaza por índice único parcial

#### Scenario: Apertura implícita

- **WHEN** el primer movimiento del día es un ingreso de liquidación
- **THEN** la caja de hoy nace abierta con `abierta_por` igual al autor

#### Scenario: Caja pendiente

- **WHEN** hay una caja anterior abierta
- **THEN** el ingreso responde `409`

#### Scenario: Caja de hoy cerrada

- **WHEN** la caja de hoy ya está cerrada
- **THEN** el ingreso responde `409`

#### Scenario: Ingreso en el cierre

- **WHEN** se cierra una caja con un ingreso de liquidación
- **THEN** `total_sistema` y `desglose` lo incluyen

#### Scenario: Migración con recibos existentes

- **WHEN** se aplica la migración sobre movimientos con recibo
- **THEN** las filas siguen válidas y no se dispara ningún trigger de inmutabilidad

### Requirement: El ingreso no habilita a cobrar por caja

Registrar el ingreso de una liquidación SHALL ser parte de la liquidación. Admin SHALL seguir
sin poder cobrar ni cerrar por `/caja`.

#### Scenario: Admin con liquidación

- **WHEN** un admin hace `POST /caja/cobrar` o `POST /caja/cierre`
- **THEN** responde `403`, igual que antes de este change

#### Scenario: Secretaria sin liquidaciones

- **WHEN** una secretaria intenta registrar el ingreso de una liquidación
- **THEN** responde `403`

## MODIFIED Requirements

### Requirement: Consulta de la caja

`GET /caja` SHALL devolver, para hoy o para `fecha`, la caja, su desglose por medio, los
ingresos y reversiones de liquidaciones, y si se puede operar. Sin `fecha` y con una caja
pendiente, SHALL devolver esa caja y el bloqueo. Consultar SHALL NOT crear filas.

#### Scenario: Caja del día con desglose

- **WHEN** hoy hubo cobros en efectivo y transferencia
- **THEN** responde `200` con el total del sistema y el subtotal de cada medio

#### Scenario: Ingresos de liquidaciones

- **WHEN** la caja tiene el ingreso de una liquidación y su reversión
- **THEN** responde cada uno con la obra social, el período, el medio y el monto con su signo, sin datos de pacientes

#### Scenario: Caja pendiente

- **WHEN** quedó abierta la caja de ayer
- **THEN** responde con `operable: false`, `bloqueo: "caja_pendiente"` y esa caja

#### Scenario: Caja de hoy cerrada

- **WHEN** ya se cerró la caja de hoy
- **THEN** responde con `operable: false` y `bloqueo: "caja_cerrada"`

#### Scenario: Consulta de un día cerrado

- **WHEN** se consulta `fecha` de un día cerrado
- **THEN** responde con sus totales, diferencia y motivo

#### Scenario: Día sin caja

- **WHEN** se consulta `fecha` de un día sin movimientos
- **THEN** responde `200` con `caja` nula

### Requirement: Pantalla de caja

`features/caja` SHALL mostrar a `secretaria` y `admin` el estado de la caja, sus totales
por medio, los recibos del día y los ingresos de liquidaciones. Solo `secretaria` SHALL ver el
cierre. Los importes y la fecha operativa SHALL provenir del servidor.

#### Scenario: Acceso desde la navegación

- **WHEN** una secretaria o un admin abre Caja
- **THEN** ve la fecha operativa, el estado, el total del sistema y el desglose por medio

#### Scenario: Ingreso visible para explicar el cierre

- **WHEN** la caja tiene el ingreso de una liquidación
- **THEN** la pantalla lo lista aparte de los recibos, con obra social, período, medio e importe

#### Scenario: Odontólogo sin pantalla

- **WHEN** un odontólogo intenta abrir Caja
- **THEN** no accede a la pantalla

#### Scenario: Bloqueo visible

- **WHEN** hay una caja pendiente
- **THEN** la pantalla indica con texto la fecha pendiente y que debe cerrarse para operar

#### Scenario: Cierre con diferencia

- **WHEN** el servidor rechaza un cierre por diferencia sin motivo
- **THEN** el formulario pide el motivo sin perder el importe cargado

#### Scenario: Cerrada sin acciones

- **WHEN** la caja de hoy está cerrada
- **THEN** la pantalla muestra contado y diferencia, sin acción de cierre

#### Scenario: Fecha sin corrimiento

- **WHEN** la pantalla muestra una `fecha` `2026-10-31` en un navegador en UTC-3
- **THEN** muestra 31/10/2026, no el día anterior
