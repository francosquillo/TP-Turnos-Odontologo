# Spec Delta — c-05-reserva-online-publica (capability modificada)

## Purpose

Ajustar `agenda-turnos-core` a lo que C-05 necesita sin cambiar su cálculo ni
su máquina: disponibilidad con variante pública y columna de token ahora
escrita por la vía online. Ver el delta de creación en
`specs/reserva-online-publica/spec.md` de este mismo change.

## MODIFIED Requirements

### Requirement: Disponibilidad como horario menos turnos con 409 y re-oferta

`GET /disponibilidad` (C-04: solo staff con `require_role`) SHALL ganar una
variante pública SIN Bearer que ejecuta el mismo `calcular_huecos` y devuelve
solo `[{inicio, fin}]` sin datos de pacientes (sin IDs de turnos, nombres ni
teléfonos), exigiendo siempre `profesional_id` (nunca vuelca la agenda
completa); la variante staff autenticada SHALL conservar su
comportamiento y RBAC sin cambios, y ambas variantes SHALL devolver los mismos
huecos para igual profesional/rango.

#### Scenario: Disponibilidad respeta horario y turnos existentes

- **WHEN** el profesional atiende lunes 08:00–12:00 en slots de 30 min y tiene un
  turno activo 09:00–09:30, y se pide disponibilidad de ese lunes
- **THEN** la respuesta incluye 08:00, 08:30, 09:30… pero no 09:00, y no incluye
  nada fuera de 08:00–12:00

#### Scenario: Carrera por el mismo hueco deja un solo ganador con re-oferta

- **WHEN** dos creaciones concurrentes piden el mismo profesional/sillón/horario
  libre
- **THEN** una responde `201` y la otra `409` con `alternativas` no vacías

#### Scenario: Variante staff sigue exigiendo Bearer

- **WHEN** se llama `GET /disponibilidad` de staff sin header Authorization en
  la ruta autenticada
- **THEN** responde `401` (la rama pública es la única sin auth)

#### Scenario: Cálculo idéntico en ambas variantes

- **WHEN** se pide el mismo profesional/rango por la variante staff y por la
  pública
- **THEN** ambas devuelven los mismos huecos `[inicio, fin)`

#### Scenario: Pública no expone pacientes y exige profesional

- **WHEN** se pide la variante pública sin `profesional_id`
- **THEN** responde `422`; y cuando responde `200` ningún elemento contiene
  datos de pacientes

### Requirement: Columna token reservada sin flujo en este change

`token_confirmacion_hash` (C-04: siempre NULL, sin endpoints que la escriban)
SHALL pasar a ser escrita por `POST /reservas` (hash SHA-256 del token) e
invalidada (NULL) por `GET /confirmar/:token` al confirmar; los turnos de
staff (`origen=secretaria|lista_espera`) SHALL mantenerla NULL y ningún
endpoint staff la SHALL exponer ni exigir; sin cambio de DDL (la columna y su
índice parcial ya existen desde C-04).

#### Scenario: Turnos creados no exponen token

- **WHEN** se crea un turno por staff y se lee su detalle
- **THEN** `token_confirmacion_hash` es nulo o ausente y no hay ningún link de
  confirmación en la respuesta

#### Scenario: Turno staff no toca el hash

- **WHEN** se crea un turno por `POST /turnos` staff y se lee su detalle
- **THEN** `token_confirmacion_hash` sigue nulo o ausente y no hay link de
  confirmación en la respuesta

#### Scenario: Turno online escribe e invalida el hash

- **WHEN** se crea por `POST /reservas` y luego se confirma por token
- **THEN** tras crear el hash es no nulo y tras confirmar vuelve a nulo
