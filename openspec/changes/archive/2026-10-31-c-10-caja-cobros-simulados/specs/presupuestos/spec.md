# Spec Delta — presupuestos

## MODIFIED Requirements

### Requirement: Máquina de estados del presupuesto

Los estados SHALL ser `borrador, presentado, aceptado, rechazado, cobrado`. Las
transiciones por API de presupuestos SHALL ser `borrador → presentado`, `presentado →
aceptado` y `presentado → rechazado`. `aceptado → cobrado` y su reversa SHALL ocurrir
solo por caja y recibos. Una transición inválida SHALL responder `409`.

#### Scenario: Presentar

- **WHEN** el autor hace `POST /presupuestos/:id/presentar` sobre un `borrador` válido
- **THEN** responde `200` con estado `presentado` y `presentado_at` del reloj del servidor

#### Scenario: Aceptar un borrador

- **WHEN** se hace `POST /presupuestos/:id/aceptar` sobre un `borrador`
- **THEN** responde `409` y no se genera ningún movimiento

#### Scenario: Reabrir un estado final

- **WHEN** se intenta presentar, aceptar o rechazar un presupuesto `aceptado`, `rechazado` o `cobrado`
- **THEN** responde `409`

#### Scenario: Estado fuera del catálogo

- **WHEN** se escribe directamente un `estado` desconocido
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Sin camino a cobrado en este change

- **WHEN** un cliente envía `estado: "cobrado"` en `POST /presupuestos` o `PUT /presupuestos/:id`
- **THEN** responde `422`

## ADDED Requirements

### Requirement: Paso a cobrado al saldar el pendiente

Un presupuesto SHALL pasar a `cobrado` en la misma transacción del cobro que deja su
pendiente exactamente en cero. Un cobro parcial SHALL NOT cambiar el estado.

#### Scenario: Cobro total

- **WHEN** se cobra de una vez el total de un presupuesto `aceptado`
- **THEN** queda `cobrado`

#### Scenario: Último parcial

- **WHEN** dos cobros parciales suman el total
- **THEN** el primero lo deja `aceptado` y el segundo `cobrado`

#### Scenario: Cobro fallido

- **WHEN** falla el cobro que iba a saldarlo
- **THEN** el presupuesto sigue `aceptado`

### Requirement: Vuelta a aceptado al anular un recibo

Anular un recibo de un presupuesto `cobrado` SHALL devolverlo a `aceptado` en la misma
transacción. El cargo original SHALL conservarse y el pendiente SHALL reflejar lo
anulado.

#### Scenario: Reversa

- **WHEN** se anula uno de los recibos de un presupuesto `cobrado`
- **THEN** queda `aceptado` con pendiente igual al monto de ese recibo

#### Scenario: Recibo de un presupuesto aún aceptado

- **WHEN** se anula un recibo de un presupuesto `aceptado`
- **THEN** sigue `aceptado` y su pendiente aumenta

#### Scenario: Se puede cobrar de nuevo

- **WHEN** un presupuesto volvió a `aceptado` por una anulación
- **THEN** se puede cobrar otra vez y un recibo nuevo lo devuelve a `cobrado`

#### Scenario: Cobrado con cargo anulado

- **WHEN** se anula el cargo de un presupuesto `cobrado`
- **THEN** sigue `cobrado` con `cargo_anulado: true`
