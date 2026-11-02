# Delta — core-models-identidad-pacientes

## ADDED Requirements

### Requirement: Plan de obra social del paciente

Un paciente SHALL tener un plan opcional, y la obra social SHALL derivarse del plan.
`PUT /pacientes/:id/plan` SHALL asignarlo o quitarlo con `plan_id` o `null`, solo para
`secretaria` y `admin`. Cambiar el plan SHALL NOT alterar presupuestos ya aceptados.

#### Scenario: Asignar plan

- **WHEN** una secretaria asigna un plan activo
- **THEN** responde `200` con el plan y su obra social

#### Scenario: Quitar plan

- **WHEN** se envía `plan_id: null`
- **THEN** el paciente queda sin plan

#### Scenario: Plan inválido

- **WHEN** el plan no existe o está inactivo
- **THEN** responde `409` y el paciente no cambia

#### Scenario: Paciente inexistente

- **WHEN** el paciente no existe o está dado de baja
- **THEN** responde `404`

#### Scenario: Odontólogo sin permiso

- **WHEN** un odontólogo llama a la ruta
- **THEN** responde `403`

## MODIFIED Requirements

### Requirement: Seed demo idempotente con datos ficticios

El sistema SHALL proveer un seed que en base limpia crea roles, 1 admin inicial
(desde `SEED_ADMIN_*`), 1 sillón demo, 1 profesional demo, y la obra social "OS Ficticia Demo"
con planes y aranceles de ejemplo. SHALL completar el código de nomenclador de los tratamientos
demo que no lo tengan. Al menos un tratamiento demo SHALL quedar sin arancel para mostrar la
revisión manual. SHALL ser idempotente: re-ejecutarlo no duplica filas ni falla en constraints
de unicidad.

#### Scenario: Doble ejecución del seed no duplica

- **WHEN** se ejecuta el seed dos veces seguidas contra la misma base
- **THEN** la segunda corrida termina sin error y los conteos de roles, usuarios,
  sillones, profesionales, obras sociales, planes y aranceles son idénticos a los de la primera

#### Scenario: Código de nomenclador sin pisar datos

- **WHEN** un tratamiento demo existente ya tiene otro código de nomenclador
- **THEN** el seed no lo modifica
