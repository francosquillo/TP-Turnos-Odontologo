# reserva-online-publica Specification

## Purpose
Dar al paciente la reserva 24/7 sin cuenta y la confirmación en 1 clic: rutas
públicas que crean turnos `pendiente` con token de un solo uso y confirman la
agenda sin intervención, para que el Flujo 1 se complete sin depender del
horario de secretaría (US-002, US-011; RN-TU-03/04/05, RN-AU-02).

## Requirements

### Requirement: Reserva pública crea turno pendiente con token

El sistema SHALL exponer `POST /reservas` SIN Bearer con esquema Pydantic
`extra='forbid'` (`profesional_id, sillon_id, inicio, fin, nombre, telefono`
requeridos; `dni, email` opcionales) que, si `[inicio, fin)` es un hueco
ofrecible actual según `calcular_huecos`, SHALL crear un turno
`origen=online` en estado `pendiente` con `sobre_turno=false` y
`creado_por=NULL`, generar un token opaco de 256 bits, persistir SOLO su hash
SHA-256 en `token_confirmacion_hash` y responder `201 {"turno_id",
"estado": "pendiente", "token", "expira_en"}`; la vía pública NUNCA SHALL
crear sobreturnos (US-002 CA-2, RN-TU-03).

#### Scenario: Reserva válida crea pendiente y devuelve token

- **WHEN** un visitante envía `POST /reservas` con profesional/sillón
  existentes, hueco libre dentro del horario, nombre y teléfono
- **THEN** responde `201`, el turno nace `pendiente` con `origen=online`, la DB
  guarda el hash (nunca el plano) y la respuesta incluye el token plano una
  única vez

#### Scenario: Esquema permisivo es rechazado

- **WHEN** se envía `POST /reservas` con un campo extra no declarado
- **THEN** responde `422` (Pydantic `extra='forbid'`)

#### Scenario: Reserva fuera del horario del profesional es rechazada

- **WHEN** se pide un `[inicio, fin)` fuera del horario de `agenda_config`
- **THEN** responde `409` (o `422`) sin crear turno (RN-TU-05)

### Requirement: Paciente mínimo con match por teléfono normalizado

El sistema SHALL exigir `nombre` (≥ 2 caracteres) y `telefono` (normalizado a
solo dígitos, mínimo 8) en `POST /reservas`; SHALL reutilizar el paciente
existente no soft-deleted con ese teléfono normalizado y, si no existe, SHALL
crear un paciente mínimo (`nombre, telefono`, resto NULL); NUNCA SHALL exigir
`dni` en la vía pública (US-002 CA-3).

#### Scenario: Teléfono conocido reutiliza paciente

- **WHEN** se reserva con un teléfono ya registrado
- **THEN** el turno referencia al paciente existente y no se crea duplicado

#### Scenario: Teléfono nuevo crea paciente mínimo

- **WHEN** se reserva con un teléfono no registrado y nombre válido
- **THEN** responde `201` y existe un paciente nuevo con ese nombre y teléfono

#### Scenario: Nombre o teléfono inválido es rechazado

- **WHEN** se envía nombre de 1 carácter o teléfono de menos de 8 dígitos
- **THEN** responde `422` y ningún turno ni paciente persiste

### Requirement: Token de un solo uso con expiración 72 h o inicio

El token SHALL expirar en `min(created_at + 72 h, inicio)` del turno (derivado
de columnas existentes, sin DDL nuevo); el plano NUNCA SHALL persistirse ni
loguearse; confirmar con éxito SHALL invalidar el token poniendo
`token_confirmacion_hash` en NULL en la misma transacción (RN-TU-04).

#### Scenario: Confirmar dentro de la ventana funciona

- **WHEN** se usa un token válido de un turno `pendiente` futuro dentro de las
  72 h de creado
- **THEN** el turno pasa a `confirmado` y el hash queda en NULL

#### Scenario: Reusar un token responde 410

- **WHEN** se usa dos veces el mismo token
- **THEN** la primera responde `200` y la segunda `410`, sin cambiar nada más

#### Scenario: Token vencido por 72 h responde 410 con contacto

- **WHEN** se usa un token más de 72 h después de creado (con `freezegun` en tests)
- **THEN** responde `410 {"detail": "token expirado", "contacto": "<teléfono>"}`
  y el turno sigue `pendiente`

#### Scenario: Token vencido por inicio responde 410

- **WHEN** se usa un token cuyo turno ya empezó aunque no pasen 72 h
- **THEN** responde `410` con alternativa de contacto y el turno no se confirma

#### Scenario: Token desconocido responde 404 sin filtrar información

- **WHEN** se usa un token que nunca existió
- **THEN** responde `404` genérico sin indicar si hubo o no un turno asociado

### Requirement: Confirmación por token actualiza la agenda sin intervención

El sistema SHALL exponer `GET /confirmar/:token` (público, más alias
`POST /confirmar/:token` con idéntica lógica) que con token válido y turno
`pendiente` SHALL aplicar la transición `pendiente→confirmado` existente y
responder `200` con solo los datos del propio turno (`estado, inicio, fin,
profesional`); si el turno ya no está `pendiente` (cancelado por secretaría)
SHALL responder `410` con detalle honesto + contacto; NUNCA SHALL exponer
turnos ajenos (RN-TU-03, US-011 CA-1/CA-2).

#### Scenario: Link confirma y la agenda lo refleja

- **WHEN** el paciente abre `GET /confirmar/:token` válido
- **THEN** responde `200` con `estado="confirmado"` y `GET /agenda` staff
  muestra el turno confirmado

#### Scenario: Turno cancelado por secretaría no se confirma

- **WHEN** el token es válido pero el turno está `cancelado`
- **THEN** responde `410` indicando que fue cancelado + teléfono del consultorio

### Requirement: Disponibilidad pública de solo lectura sin datos de pacientes

El sistema SHALL exponer `GET /disponibilidad` SIN Bearer con los mismos
parámetros (`profesional_id` siempre requerido, `desde, hasta[, sillon_id,
duracion_min]`) que devuelve SOLO `[{inicio, fin}]` calculados con
`calcular_huecos` (sin IDs de turnos, nombres ni teléfonos); fuera de horario
SHALL devolver lista vacía (RN-TU-05, US-002 CA-1).

#### Scenario: Pública muestra huecos sin pacientes

- **WHEN** se pide `GET /disponibilidad` pública sin Authorization para un
  profesional y un día con un turno ocupado a las 09:00
- **THEN** responde `200` con huecos que excluyen 09:00 y ningún elemento
  contiene datos de pacientes

#### Scenario: Pública exige profesional

- **WHEN** se pide disponibilidad sin `profesional_id`
- **THEN** responde `422` (nunca vuelca la agenda completa)

### Requirement: Carrera por el mismo hueco deja un ganador con re-oferta

Ante dos `POST /reservas` concurrentes (o reserva + creación staff) por el
mismo profesional/sillón/horario libre, el sistema SHALL persistir un solo
turno (la DB con EXCLUDE decide) y la perdedora SHALL responder `409
{"detail": "hueco ocupado", "alternativas": [...]}` con huecos próximos no
vacíos (Flujo 1, RN-TU-01).

#### Scenario: Doble reserva concurrente deja un solo turno

- **WHEN** dos reservas concurrentes piden el mismo hueco libre contra PG real
- **THEN** una responde `201`, la otra `409` con `alternativas`, y solo un
  turno persiste

### Requirement: Frontend público reserva, confirma y aterriza

El sistema SHALL ofrecer `GET /` landing pública (links a `/reservas` y
`/seguridad`), `pages/reservas` (selector profesional/día/hora desde
disponibilidad pública + formulario mínimo + éxito con aviso de WhatsApp +
`409` con re-oferta sin perder el formulario) y `pages/confirmar`
(`cargando|confirmado|expirado|invalido`; expirado/inválido muestran el
teléfono del consultorio); todas SIN Bearer, tipado TS estricto sin `any`
(US-002, US-011 CA-2).

#### Scenario: 409 en la UI re-oferta sin perder datos

- **WHEN** el hueco elegido se ocupa antes de enviar y la API responde `409`
- **THEN** la página muestra las alternativas y conserva nombre/teléfono
  ingresados

#### Scenario: Token expirado muestra contacto

- **WHEN** se abre `/confirmar/:token` expirado
- **THEN** la pantalla muestra el teléfono del consultorio en vez del resumen
