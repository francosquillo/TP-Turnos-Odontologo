# Spec Delta — notificaciones-whatsapp

## ADDED Requirements

### Requirement: Reseña Google al marcar un turno como asistido

Cuando un turno pasa a `asistido` y `GOOGLE_REVIEW_URL` está configurada, el sistema SHALL
encolar una única notificación `resena_google` para ese turno con la plantilla existente, con
`link_resena` igual a esa URL y sin datos clínicos (RN-CL-04, RN-NO-04). El encolado SHALL ser
idempotente por turno y tipo, como los demás tipos. El sistema NUNCA SHALL escribir reseñas ni
llamar APIs de Google: solo envía el link. Sin `GOOGLE_REVIEW_URL`, o sin teléfono válido del
paciente, no se encola nada y el cambio de estado del turno SHALL completarse igual.

#### Scenario: Asistido con link configurado

- **WHEN** `GOOGLE_REVIEW_URL` tiene valor y un odontólogo marca `asistido` su turno
- **THEN** existe una notificación `resena_google` para ese turno con el link en el payload y sin pieza, hallazgo ni diagnóstico

#### Scenario: Marcar dos veces no duplica

- **WHEN** el encolado de la reseña se intenta dos veces para el mismo turno
- **THEN** existe una sola notificación `resena_google` para ese turno

#### Scenario: Sin link configurado

- **WHEN** `GOOGLE_REVIEW_URL` está vacía y se marca `asistido`
- **THEN** el turno queda `asistido` y no se crea ninguna notificación `resena_google`
