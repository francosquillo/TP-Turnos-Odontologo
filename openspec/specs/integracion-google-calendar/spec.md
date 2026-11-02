# integracion-google-calendar Specification

## Purpose
Deja visible el estado de la sincronización con Google Calendar por profesional detrás de un
flag, sin OAuth ni sincronización real en v1.0, para que la demo no prometa algo inexistente.

## Requirements

### Requirement: Estado de Google Calendar detrás de un flag

El sistema SHALL exponer `GET /integraciones/google-calendar` para usuarios autenticados, que
informa `habilitado=false` con un mensaje claro cuando falta `GCAL_CLIENT_ID` o `GCAL_SECRET`.
Con ambas variables presentes SHALL informar que las credenciales están configuradas y que la
sincronización por profesional queda para después del TP. El sistema NUNCA SHALL llamar a
Google en v1.0 ni devolver las credenciales.

#### Scenario: Sin credenciales

- **WHEN** `GCAL_CLIENT_ID` está vacía y un usuario autenticado consulta el estado
- **THEN** responde `habilitado=false` con un mensaje de deshabilitado

#### Scenario: Con credenciales

- **WHEN** ambas variables tienen valor
- **THEN** responde que las credenciales están configuradas, que la sincronización no está activa en v1.0, y no incluye sus valores

#### Scenario: Sin login

- **WHEN** un cliente sin token consulta el estado
- **THEN** responde `401`
