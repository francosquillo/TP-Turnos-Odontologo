# agenda-turnos-core Specification

## Purpose
Dar a la secretaría la agenda operable sin papel: turnos persistidos con choque
imposible por profesional y por sillón a nivel DB, estados con transiciones
cerradas, disponibilidad calculada desde el horario del profesional y vistas
día/semana/mes con reprogramación que revalida solapamiento, para que el flujo
de atención (Flujo 1 parcial staff) ocurra sobre datos concurrentemente seguros
(US-001, US-003; RN-TU-01/02/03/05).

## Requirements

### Requirement: Modelo Turno con doble anti-solapamiento a nivel DB

El sistema SHALL persistir `turno (paciente_id, profesional_id, sillon_id,
inicio, fin, estado, origen, token_confirmacion_hash nullable, sobre_turno bool,
motivo_sobreturno nullable, motivo_cancelacion nullable)` con `fin > inicio`,
FKs a paciente/profesional/sillón existentes, y SHALL garantizar con dos
constraints parciales `EXCLUDE USING gist (profesional_id WITH =,
tstzrange(inicio, fin) WITH &&)` e ídem `(sillon_id, rango)` con predicado
`WHERE (sobre_turno IS FALSE AND estado IN
('pendiente','confirmado','asistido'))` que ningún par de turnos activos
no-sobreturno se solape por profesional ni por sillón (RN-TU-01, DD-03).

#### Scenario: Dos turnos solapados del mismo profesional son imposibles

- **WHEN** existe un turno activo del profesional P de 10:00 a 10:30 y se crea
  otro turno activo de P de 10:15 a 10:45
- **THEN** la operación es rechazada (pre-chequeo `409` o constraint DB) y solo
  el primer turno persiste

#### Scenario: Dos turnos solapados en el mismo sillón son imposibles

- **WHEN** existe un turno activo en el sillón S de 10:00 a 10:30 y se crea otro
  turno activo en S de 10:15 a 10:45 (aunque sea de distinto profesional)
- **THEN** la operación es rechazada y solo el primer turno persiste

#### Scenario: Turnos cancelados liberan el hueco

- **WHEN** un turno de 10:00 a 10:30 está en estado `cancelado` y se crea un
  turno activo en el mismo profesional/sillón de 10:00 a 10:30
- **THEN** la creación responde `201` (el cancelado no participa del EXCLUDE)

#### Scenario: Turnos contiguos no colisionan

- **WHEN** existe un turno activo de 10:00 a 10:30 y se crea otro de 10:30 a 11:00
  mismo profesional y sillón
- **THEN** la creación responde `201` (los rangos medio-abiertos no se solapan)

### Requirement: Sobreturno solo con flag explícito, motivo y auditoría

El sistema SHALL permitir crear o reprogramar un turno solapado solo si el body
trae `sobre_turno=true` **y** `motivo_sobreturno` no vacío, y SHALL persistir
junto al turno `motivo_sobreturno`, `creado_por` (usuario del JWT) y
`created_at` visibles en `TurnoOut` para auditoría; sin flag o sin motivo ante
solapamiento SHALL responder `409` (RN-TU-02, RN-GL-02).

#### Scenario: Solapamiento con flag y motivo crea sobreturno auditado

- **WHEN** se crea un turno solapado con `sobre_turno=true` y motivo
  `"urgencia con dolor"` como secretaria autenticada
- **THEN** responde `201`, el turno tiene `sobre_turno=true`, y su detalle
  muestra motivo + usuario creador + fecha

#### Scenario: Solapamiento sin motivo es rechazado aunque venga el flag

- **WHEN** se crea un turno solapado con `sobre_turno=true` pero sin motivo
- **THEN** responde `409` (o `422` por esquema) y ningún turno nuevo persiste

#### Scenario: Solapamiento sin flag es rechazado aunque haya hueco parcial

- **WHEN** se crea un turno solapado sin `sobre_turno`
- **THEN** responde `409` con `alternativas` de huecos próximos

### Requirement: CRUD de turnos con esquemas estrictos y RBAC staff

El sistema SHALL exponer `CRUD /turnos` (`POST` crea `201`, `GET /:id` y
`GET /` listan, `PATCH /:id` edita horario con revalidación, sin `DELETE` de
negocio) con esquemas Pydantic `extra='forbid'`, validando `fin > inicio` y FKs
existentes (`422` si fallan), protegido por `require_role` según matriz D-07
(`admin|secretaria` completo, `odontologo` lectura + estado de propios; sin
Bearer `401`, rol insuficiente `403`).

#### Scenario: Crear turno válido responde 201

- **WHEN** una secretaria crea un turno con paciente, profesional y sillón
  existentes, `fin > inicio` y sin solapamiento
- **THEN** responde `201` con el turno en estado inicial según `origen`
  (staff → `confirmado` por defecto, ver Requirement de estados)

#### Scenario: Esquema permisivo es rechazado

- **WHEN** se envía `POST /turnos` con un campo extra no declarado
- **THEN** responde `422` (Pydantic `extra='forbid'`)

#### Scenario: Sin Bearer no hay acceso a turnos

- **WHEN** se llama `GET /turnos` sin header Authorization
- **THEN** responde `401`

### Requirement: Máquina de estados con transiciones cerradas y cancelación motivada

Todo turno SHALL tener `estado pendiente|confirmado|asistido|ausente|cancelado`;
el sistema SHALL exponer `PATCH /turnos/:id/estado {estado[, motivo]}` que solo
acepta las transiciones `pendiente→confirmado|cancelado`,
`confirmado→asistido|ausente|cancelado` (más `pendiente→asistido` solo por
`admin` para carga histórica), exige `motivo` no vacío al pasar a `cancelado`,
y responde `422` ante transición ilegal; los estados
`asistido|ausente|cancelado` SHALL ser terminales (RN-TU-03). Crear desde staff
(`origen=secretaria`) nace `confirmado`; el `origen=online|lista_espera` nace
`pendiente` (el flujo a `confirmado` vía token es C-05).

#### Scenario: Confirmar un pendiente funciona

- **WHEN** se envía `PATCH /turnos/:id/estado {estado: "confirmado"}` sobre un
  turno `pendiente`
- **THEN** responde `200` con `estado="confirmado"`

#### Scenario: Cancelar sin motivo es rechazado

- **WHEN** se envía `PATCH /turnos/:id/estado {estado: "cancelado"}` sin motivo
- **THEN** responde `422` y el turno sigue en su estado anterior

#### Scenario: Transición terminal es rechazada

- **WHEN** se envía `PATCH /turnos/:id/estado {estado: "confirmado"}` sobre un
  turno `asistido`
- **THEN** responde `422` y el estado no cambia

### Requirement: Disponibilidad como horario menos turnos con 409 y re-oferta

El sistema SHALL exponer
`GET /disponibilidad?profesional_id&desde&hasta[&sillon_id&duracion_min]` que
calcula huecos ofrecibles como horario semanal de `agenda_config` del
profesional menos turnos activos no-sobreturno (del profesional y del sillón si
se pide), solo dentro del horario (fuera de horario → lista vacía, RN-TU-05), y
SHALL responder `409 {"detail": "hueco ocupado", "alternativas": [...]}` con
huecos próximos ante colisión concurrente en creación (Flujo 1).

#### Scenario: Disponibilidad respeta horario y turnos existentes

- **WHEN** el profesional atiende lunes 08:00–12:00 en slots de 30 min y tiene un
  turno activo 09:00–09:30, y se pide disponibilidad de ese lunes
- **THEN** la respuesta incluye 08:00, 08:30, 09:30… pero no 09:00, y no incluye
  nada fuera de 08:00–12:00

#### Scenario: Carrera por el mismo hueco deja un solo ganador con re-oferta

- **WHEN** dos creaciones concurrentes piden el mismo profesional/sillón/horario
  libre
- **THEN** una responde `201` y la otra `409` con `alternativas` no vacías

### Requirement: Agenda por vistas día/semana/mes

El sistema SHALL exponer
`GET /agenda?vista=dia|semana|mes&fecha&profesional_id&sillon_id` que devuelve
los turnos activos del período con `{id, inicio, fin, estado, paciente,
profesional, sillon}`, y el frontend SHALL ofrecer vistas día/semana/mes con
colores por estado (US-001 CA-1/CA-2).

#### Scenario: Vista día lista los turnos del profesional

- **WHEN** se pide `GET /agenda?vista=dia&fecha=2026-10-13&profesional_id=P`
- **THEN** responde `200` con los turnos de P de ese día ordenados por `inicio`,
  cada uno con su `estado`

#### Scenario: Vista con parámetro inválido es rechazada

- **WHEN** se pide `GET /agenda?vista=anio`
- **THEN** responde `422`

### Requirement: Reprogramar revalida solapamiento y cancelar exige motivo

Reprogramar (`PATCH /turnos/:id {inicio, fin}`) SHALL revalidar horario +
solapamiento exactamente como la creación (incluida la vía sobreturno con
motivo) excluyendo el propio turno, y cancelar SHALL ser cambio de estado a
`cancelado` con motivo (nunca borrado físico, RN-GL-01); la UI SHALL hacer drag
para reprogramar con rollback ante `409` mostrando las alternativas (US-003
CA-1/CA-2).

#### Scenario: Reprogramar a hueco ocupado es rechazado

- **WHEN** se reprograma un turno a un horario solapado con otro turno activo
  del mismo profesional sin flag de sobreturno
- **THEN** responde `409` con `alternativas` y el turno conserva su horario
  original

#### Scenario: Reprogramar a hueco libre funciona

- **WHEN** se reprograma un turno a un horario libre dentro del horario del
  profesional
- **THEN** responde `200` con el nuevo `inicio/fin`

### Requirement: Columna token reservada sin flujo en este change

La migración SHALL crear `token_confirmacion_hash TEXT NULLABLE` con índice
parcial `WHERE token_confirmacion_hash IS NOT NULL`, y en este change la columna
SHALL permanecer siempre `NULL` (ningún endpoint la escribe ni la exige); el
flujo de confirmación por token un solo uso con expiración es C-05 (RN-TU-04).

#### Scenario: Turnos creados no exponen token

- **WHEN** se crea un turno por staff y se lee su detalle
- **THEN** `token_confirmacion_hash` es nulo o ausente y no hay ningún link de
  confirmación en la respuesta
