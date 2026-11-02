# Spec Delta — seguridad-publica

## Purpose

Da al consultorio una página pública, sin login, que cuenta cómo se protegen los datos con
afirmaciones verificables contra la configuración real del sistema (US-052).

## ADDED Requirements

### Requirement: Endpoint público de seguridad con hechos verificables

El sistema SHALL exponer `GET /seguridad` sin autenticación. La respuesta SHALL incluir al
menos: que los datos son 100 % ficticios y de prueba; el algoritmo de hash de contraseñas; la
vida del access token en minutos, tomada de la configuración vigente; si WhatsApp opera en modo
mock; si Google Calendar está habilitado; qué acciones quedan auditadas; y cómo se respaldan los
datos. Cada afirmación SHALL corresponder a algo que el sistema hace en ese momento. La
respuesta NUNCA SHALL afirmar cifrado en reposo ni TLS mientras el despliegue sea local, y
NUNCA SHALL incluir secretos, credenciales ni datos de pacientes.

#### Scenario: Acceso sin login

- **WHEN** un cliente sin token llama `GET /seguridad`
- **THEN** responde `200` con la declaración de datos ficticios en `true`

#### Scenario: La vida del token refleja la configuración

- **WHEN** `JWT_EXPIRE_MIN` vale `15` y se llama `GET /seguridad`
- **THEN** la respuesta informa `15` minutos

#### Scenario: Sin secretos en la respuesta

- **WHEN** `JWT_SECRET`, `WHATSAPP_TOKEN` y `GCAL_SECRET` tienen valores y se llama `GET /seguridad`
- **THEN** ninguno de esos valores aparece en el cuerpo de la respuesta

#### Scenario: Sin afirmaciones falsas de cifrado

- **WHEN** se llama `GET /seguridad` en el despliegue local
- **THEN** la respuesta no declara cifrado en reposo ni TLS activos, y lo informa como pendiente para producción

### Requirement: Página pública de seguridad

El frontend SHALL mostrar en la página pública `Seguridad` el contenido de `GET /seguridad`,
accesible desde la landing y sin sesión. Si el endpoint no responde, SHALL mostrar un mensaje
de error en lugar de afirmaciones por defecto.

#### Scenario: Visitante sin sesión ve la página

- **WHEN** un visitante sin sesión abre Seguridad desde la landing
- **THEN** ve la declaración de datos ficticios y los hechos devueltos por el backend

#### Scenario: Backend caído

- **WHEN** `GET /seguridad` falla
- **THEN** la página muestra un error y no muestra afirmaciones de seguridad
