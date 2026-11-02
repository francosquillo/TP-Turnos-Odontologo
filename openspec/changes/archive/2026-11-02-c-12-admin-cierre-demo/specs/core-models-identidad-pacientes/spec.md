# Spec Delta — core-models-identidad-pacientes

## MODIFIED Requirements

### Requirement: Seed demo idempotente con datos ficticios

El sistema SHALL proveer un seed que en base limpia crea roles, 1 admin inicial
(desde `SEED_ADMIN_*`), 1 sillón demo, 1 profesional demo, y la obra social "OS Ficticia Demo"
con planes y aranceles de ejemplo. SHALL completar el código de nomenclador de los tratamientos
demo que no lo tengan. Al menos un tratamiento demo SHALL quedar sin arancel para mostrar la
revisión manual. SHALL crear además pacientes demo ficticios, identificados por DNI y teléfono
claramente de prueba, con al menos uno asociado a un plan de "OS Ficticia Demo", para que una
reserva online con su teléfono reutilice ese paciente y el flujo llegue a la liquidación. El
seed NUNCA SHALL crear cajas, movimientos de caja ni recibos, para no dejar una caja pendiente
que bloquee la operación del día (RN-CO-01). SHALL ser idempotente: re-ejecutarlo no duplica
filas ni falla en constraints de unicidad.

#### Scenario: Doble ejecución del seed no duplica

- **WHEN** se ejecuta el seed dos veces seguidas contra la misma base
- **THEN** la segunda corrida termina sin error y los conteos de roles, usuarios,
  sillones, profesionales, pacientes, obras sociales, planes y aranceles son idénticos a los de la primera

#### Scenario: Código de nomenclador sin pisar datos

- **WHEN** un tratamiento demo existente ya tiene otro código de nomenclador
- **THEN** el seed no lo modifica

#### Scenario: Paciente demo con plan listo para el recorrido

- **WHEN** se ejecuta el seed en base limpia
- **THEN** existe al menos un paciente demo con plan de "OS Ficticia Demo" y un teléfono ficticio válido para la reserva online

#### Scenario: El seed no toca la caja

- **WHEN** se ejecuta el seed en base limpia
- **THEN** no existen cajas, movimientos de caja ni recibos, y el primer cobro del día no responde `409` por caja pendiente
