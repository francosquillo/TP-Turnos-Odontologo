# Spec Delta — auth-rbac

## MODIFIED Requirements

### Requirement: Resguardo del último admin expuesto vía HTTP

El sistema SHALL bloquear con `409` la desactivación (`PATCH
/admin/usuarios/:id/desactivar`), la eliminación (`DELETE /admin/usuarios/:id`) y el cambio de
rol a uno distinto de `admin` (`PATCH /admin/usuarios/:id`) del único admin activo,
reutilizando el guard de servicio de C-02; con otro admin activo la operación SHALL tener éxito
(RN-AU-03). El guard SHALL mantenerse ante operaciones concurrentes: dos operaciones simultáneas
que dejarían sin admins activos NUNCA SHALL tener éxito las dos. `DELETE` sobre un usuario que
tiene historial referenciado SHALL responder `409` indicando que debe desactivarse, sin borrar
nada (RN-GL-01). Solo `admin` puede llamar estos endpoints.

#### Scenario: Desactivar al único admin activo vía HTTP es bloqueado

- **WHEN** existe un único admin activo y un admin llama `PATCH /admin/usuarios/:id/desactivar` sobre él
- **THEN** responde `409` y el usuario sigue con `activo=true`

#### Scenario: Eliminar al único admin activo vía HTTP es bloqueado

- **WHEN** existe un único admin activo y un admin llama `DELETE /admin/usuarios/:id` sobre él
- **THEN** responde `409` y el usuario sigue existiendo y activo

#### Scenario: Con dos admins desactivar uno funciona

- **WHEN** existen dos admins activos y se desactiva uno vía `PATCH /admin/usuarios/:id/desactivar`
- **THEN** responde `200` con `activo=false` y el otro admin sigue activo

#### Scenario: Quitar el rol admin al único admin activo es bloqueado

- **WHEN** existe un único admin activo y un admin cambia su rol a `secretaria` con `PATCH /admin/usuarios/:id`
- **THEN** responde `409` y el usuario sigue siendo admin activo

#### Scenario: Dos desactivaciones concurrentes no dejan el sistema sin admins

- **WHEN** existen exactamente dos admins activos y se desactivan los dos en paralelo contra Postgres real
- **THEN** una operación responde `200`, la otra `409`, y queda un admin activo

#### Scenario: Eliminar un usuario con historial responde 409

- **WHEN** un admin elimina un usuario que emitió un recibo o creó un turno
- **THEN** responde `409` indicando desactivar, y el usuario y su historial siguen intactos
