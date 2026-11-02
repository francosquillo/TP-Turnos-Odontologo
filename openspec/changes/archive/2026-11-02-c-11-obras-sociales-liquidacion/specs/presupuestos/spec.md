# Delta — presupuestos

## ADDED Requirements

### Requirement: Cobertura congelada al aceptar

Al aceptar un presupuesto de un paciente con plan activo de una obra social activa, el sistema
SHALL guardar el plan y, por ítem, el arancel vigente en el día operativo de la aceptación y
el monto cubierto, en la misma transacción. El monto cubierto SHALL ser el menor entre el
arancel y el precio del ítem, por la cantidad. Sin arancel, el monto cubierto SHALL ser cero.
Un cambio posterior de arancel o de plan SHALL NOT alterar lo congelado. Sin plan, `aceptar`
SHALL comportarse como antes.

#### Scenario: Cobertura parcial

- **WHEN** se acepta un ítem de precio 18000.00, cantidad 2 y arancel vigente 12600.00
- **THEN** el ítem queda con ese arancel y `25200.00` cubierto

#### Scenario: Ítem sin arancel

- **WHEN** un ítem no tiene arancel vigente
- **THEN** queda sin arancel y con `0.00` cubierto, y los demás ítems se cubren normalmente

#### Scenario: Paciente sin plan

- **WHEN** se acepta el presupuesto de un paciente sin plan
- **THEN** no se guarda plan ni arancel, y existe solo el cargo

#### Scenario: Plan inactivo

- **WHEN** el plan o su obra social están inactivos
- **THEN** se acepta como un paciente sin plan

#### Scenario: Fallo en la cobertura

- **WHEN** falla el registro de la cobertura
- **THEN** el presupuesto sigue `presentado`, sin cargo ni cobertura

## MODIFIED Requirements

### Requirement: Máquina de estados del presupuesto

Los estados SHALL ser `borrador, presentado, aceptado, rechazado, cobrado`. Las
transiciones por API de presupuestos SHALL ser `borrador → presentado`, `presentado →
aceptado` y `presentado → rechazado`. `aceptado → cobrado` SHALL ocurrir por caja, o al
aceptar cuando la cobertura salda todo el importe. Su reversa SHALL ocurrir solo por recibos.
Una transición inválida SHALL responder `409`.

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

### Requirement: Paso a cobrado al saldar el pendiente

Un presupuesto SHALL pasar a `cobrado` en la misma transacción del cobro o de la cobertura que
deja su pendiente exactamente en cero. Un cobro parcial o una cobertura parcial SHALL NOT
cambiar el estado a `cobrado`.

#### Scenario: Cobro total

- **WHEN** se cobra de una vez el total de un presupuesto `aceptado`
- **THEN** queda `cobrado`

#### Scenario: Último parcial

- **WHEN** dos cobros parciales suman el total
- **THEN** el primero lo deja `aceptado` y el segundo `cobrado`

#### Scenario: Cobro fallido

- **WHEN** falla el cobro que iba a saldarlo
- **THEN** el presupuesto sigue `aceptado`

#### Scenario: Cobertura total

- **WHEN** la cobertura iguala el total al aceptar
- **THEN** queda `cobrado`, sin recibo, con un cargo y un ajuste que dejan el pendiente en cero

#### Scenario: Cobertura parcial

- **WHEN** la cobertura es menor que el total
- **THEN** queda `aceptado`, y el pendiente es lo que queda a cargo del paciente
