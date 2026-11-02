# auditoria-admin Specification

## Purpose
Registra quién hizo qué y cuándo en las acciones administrativas que RN-GL-02 pide auditar y
que el sistema todavía no registra ("accesos admin"): gestión de usuarios, importación y
exportación total.

## Requirements

### Requirement: Registro append-only de acciones admin

El sistema SHALL registrar un evento con actor, acción, tipo y id del objeto, detalle sin datos
clínicos ni contraseñas y fecha y hora, en la misma transacción que cada una de estas acciones
exitosas: alta, edición, desactivación y eliminación de usuario; importación de pacientes; y
exportación total. Una acción rechazada (`4xx`) NO SHALL registrar evento. Los eventos NUNCA
SHALL modificarse ni borrarse: la base SHALL rechazar `UPDATE` y `DELETE` sobre ellos.

#### Scenario: Alta de usuario auditada

- **WHEN** un admin crea un usuario
- **THEN** existe un evento con ese admin como actor, la acción de alta y el id del usuario creado, sin la contraseña

#### Scenario: Acción rechazada no audita

- **WHEN** el resguardo del último admin rechaza una desactivación con `409`
- **THEN** no se registra ningún evento

#### Scenario: Evento inmutable

- **WHEN** se intenta `UPDATE` o `DELETE` sobre un evento directamente en Postgres
- **THEN** la base rechaza la operación

### Requirement: Consulta de la auditoría por admin

El sistema SHALL exponer `GET /admin/auditoria`, solo para `admin`, que lista los eventos del
más reciente al más antiguo, con paginación por `limit` y `offset`.

#### Scenario: Admin consulta

- **WHEN** un admin llama `GET /admin/auditoria` después de crear un usuario
- **THEN** el primer evento de la lista es esa alta

#### Scenario: Otro rol

- **WHEN** una secretaria llama `GET /admin/auditoria`
- **THEN** responde `403`
