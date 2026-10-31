# Spec Delta — recibos

## Purpose

Emitir comprobantes de cobro con numeración consecutiva sin huecos, que no se borran ni
se alteran, y anularlos solo por contramovimiento con motivo (RN-CO-02, RN-CO-04).

## ADDED Requirements

### Requirement: Numeración sin huecos

Cada recibo SHALL recibir el número siguiente al último emitido, empezando en 1 y sin
saltos. Un cobro que falla SHALL NOT consumir número. El número SHALL ser único.

#### Scenario: Consecutivos

- **WHEN** se hacen tres cobros seguidos
- **THEN** los recibos tienen números 1, 2 y 3

#### Scenario: Rollback no deja hueco

- **WHEN** falla un cobro después de pedir número y luego se hace otro cobro
- **THEN** los números siguen siendo consecutivos

#### Scenario: Rechazos no dejan hueco

- **WHEN** entre dos cobros válidos hay uno rechazado por sobrepago
- **THEN** los números siguen siendo consecutivos

#### Scenario: Concurrencia

- **WHEN** veinte sesiones cobran a la vez sobre presupuestos distintos
- **THEN** los recibos tienen exactamente los números de 1 a 20, sin repetidos

#### Scenario: Cambio de día

- **WHEN** se emiten recibos en dos días distintos
- **THEN** la numeración continúa sin reiniciarse

#### Scenario: Número duplicado

- **WHEN** se inserta directamente un recibo con un número existente
- **THEN** la DB lo rechaza por UNIQUE

### Requirement: Recibo inmutable

Un recibo SHALL NOT poder borrarse, tampoco por SQL directo. La única modificación
admitida SHALL ser pasar una vez a anulado con motivo, autor y fecha. Su número, monto,
medio y paciente SHALL NOT cambiar nunca.

#### Scenario: DELETE directo

- **WHEN** se ejecuta `DELETE` sobre un recibo
- **THEN** la DB lo rechaza

#### Scenario: Cambio de monto

- **WHEN** se ejecuta `UPDATE` directo del `monto` de un recibo
- **THEN** la DB lo rechaza

#### Scenario: Cambio de número en la anulación

- **WHEN** un `UPDATE` directo anula un recibo y además cambia su `numero`
- **THEN** la DB lo rechaza

#### Scenario: Desanular

- **WHEN** se ejecuta `UPDATE` directo que vuelve `anulado` a falso
- **THEN** la DB lo rechaza

#### Scenario: Anulado sin motivo

- **WHEN** se escribe directamente un recibo anulado sin motivo
- **THEN** la DB lo rechaza por CHECK

### Requirement: Anulación por contramovimiento

`POST /recibos/:id/anular` SHALL exigir `motivo` y, en una transacción, marcar el recibo
anulado, crear un `ajuste` opuesto al `pago` con `anula_a_id`, y crear un movimiento de
caja negativo con el medio original. El número SHALL conservarse.

#### Scenario: Anulación exitosa

- **WHEN** un admin anula un recibo de 400.00 con `motivo`
- **THEN** responde `200` con el recibo anulado, y el saldo del paciente sube 400.00

#### Scenario: Número conservado

- **WHEN** se anula el recibo 7 y luego se cobra otro
- **THEN** el recibo 7 sigue existiendo anulado y el nuevo es el 8

#### Scenario: Trazabilidad

- **WHEN** se anula un recibo
- **THEN** guarda motivo, autor y fecha, y el `ajuste` referencia el `pago` y el recibo

#### Scenario: Sin motivo

- **WHEN** se anula sin `motivo`
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Doble anulación

- **WHEN** se anula otra vez el mismo recibo
- **THEN** responde `409`

#### Scenario: Doble anulación concurrente

- **WHEN** dos sesiones anulan el mismo recibo a la vez
- **THEN** una responde `200`, la otra `409`, y hay un solo contramovimiento

#### Scenario: Recibo inexistente

- **WHEN** el recibo no existe
- **THEN** responde `404`

### Requirement: La anulación no toca cajas cerradas

La reversión SHALL registrarse en la caja del día en que se anula. Una caja cerrada
SHALL conservar sus totales. Si la caja de hoy está cerrada o hay una caja pendiente de
un día anterior, la anulación SHALL responder `409` sin cambios.

#### Scenario: Anular el mismo día

- **WHEN** se anula un recibo de hoy con la caja abierta
- **THEN** la reversión cae en la misma caja y `total_sistema` ya no incluye ese importe

#### Scenario: Anular un recibo de un día cerrado

- **WHEN** hoy se anula un recibo de una caja ya cerrada
- **THEN** los totales de esa caja no cambian y la reversión cae en la caja de hoy

#### Scenario: La anulación abre la caja

- **WHEN** se anula un recibo viejo en un día sin movimientos
- **THEN** se abre la caja de hoy con `abierta_por` igual al admin y total negativo

#### Scenario: Caja de hoy cerrada

- **WHEN** se intenta anular con la caja de hoy ya cerrada
- **THEN** responde `409` y el recibo no cambia

#### Scenario: Caja pendiente

- **WHEN** se intenta anular con una caja anterior sin cerrar
- **THEN** responde `409` y el recibo no cambia

### Requirement: Consulta de recibos

`GET /recibos?fecha=` SHALL listar los recibos emitidos en la caja de esa fecha, del
número mayor al menor, con número, paciente, monto, medio, anulación y fecha de emisión.
`fecha` SHALL ser obligatoria.

#### Scenario: Recibos del día

- **WHEN** se consulta una fecha con recibos, uno de ellos anulado
- **THEN** responde `200` con todos, y el anulado con `anulado: true` y su motivo

#### Scenario: Anulado otro día

- **WHEN** un recibo del 30/10 se anula el 31/10
- **THEN** sigue listado en el 30/10 y no aparece como emitido el 31/10

#### Scenario: Sin fecha

- **WHEN** se llama sin `fecha`
- **THEN** responde `422`

### Requirement: Permisos sobre recibos

`POST /recibos/:id/anular` SHALL permitirse solo a `admin`. `GET /recibos` SHALL
permitirse a `secretaria` y `admin`. `odontologo` SHALL NOT acceder. Sin Bearer válido
SHALL responder `401`.

#### Scenario: Secretaria no anula

- **WHEN** una secretaria intenta anular un recibo
- **THEN** responde `403` y nada cambia

#### Scenario: Secretaria lista

- **WHEN** una secretaria hace `GET /recibos?fecha=`
- **THEN** responde `200`

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo llama a cualquier ruta de `/recibos`
- **THEN** responde `403`

#### Scenario: Sin autenticación

- **WHEN** se llama a `/recibos` sin Bearer
- **THEN** responde `401`

### Requirement: Sin datos clínicos en recibos

El recibo SHALL NOT contener piezas, hallazgos ni tratamientos. Los movimientos generados
SHALL usar un `concepto` fijo con el número de recibo. Los motivos SHALL NOT escribirse
en logs ni viajar en la URL.

#### Scenario: Concepto del pago

- **WHEN** se genera el `pago` del recibo 12
- **THEN** `concepto` es `Recibo 12`

#### Scenario: Concepto de la anulación

- **WHEN** se anula el recibo 12
- **THEN** el `ajuste` tiene `concepto` `Anulación del recibo 12`

#### Scenario: Motivo fuera de los logs

- **WHEN** se anula con un texto marcador en `motivo`
- **THEN** ningún registro de log capturado contiene ese texto

### Requirement: Comprobante en pantalla

Después de cobrar, la pantalla SHALL mostrar número, paciente, importe, medio y fecha del
recibo, e indicar que el pago es simulado. Los recibos del día SHALL listarse en Caja, y
solo `admin` SHALL ver la acción de anular.

#### Scenario: Comprobante tras cobrar

- **WHEN** una secretaria completa un cobro
- **THEN** ve el comprobante con el número y la leyenda de pago simulado

#### Scenario: Secretaria sin anular

- **WHEN** una secretaria ve la lista de recibos
- **THEN** no tiene acción de anular

#### Scenario: Admin anula con motivo

- **WHEN** un admin anula un recibo sin escribir motivo
- **THEN** el formulario no se envía e indica que el motivo es obligatorio

#### Scenario: Recibo anulado visible

- **WHEN** la lista incluye un recibo anulado
- **THEN** se indica con texto que está anulado, junto con su motivo
