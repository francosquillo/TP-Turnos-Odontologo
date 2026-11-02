# Spec Delta — admin-usuarios

## Purpose

Permite al admin (Dueño como alias) dar de alta, editar y reactivar usuarios del consultorio
con uno de los tres roles fijos, desde la API y desde el panel admin (US-050).

## ADDED Requirements

### Requirement: Alta de usuario por admin

El sistema SHALL exponer `POST /admin/usuarios`, solo para `admin`, con `nombre`, `email`,
`password` y `rol` (`admin`, `odontologo` o `secretaria`). SHALL rechazar con `422` campos
extra, un rol fuera del catálogo o una contraseña de menos de 8 caracteres, y con `409` un
email que ya exista sin distinguir mayúsculas. La contraseña SHALL guardarse con el mismo hash
que el login y NUNCA SHALL devolverse. El usuario nace activo.

#### Scenario: Alta válida

- **WHEN** un admin crea un usuario `secretaria` con email nuevo y contraseña de 8 caracteres o más
- **THEN** responde `201` con id, nombre, email, rol y `activo=true`, sin contraseña ni hash, y el usuario puede iniciar sesión

#### Scenario: Email repetido

- **WHEN** un admin crea un usuario con un email que ya existe con otras mayúsculas
- **THEN** responde `409` y no se crea ningún usuario

#### Scenario: Rol fuera de catálogo o campo extra

- **WHEN** el cuerpo trae `rol="duenio"` o un campo no declarado
- **THEN** responde `422`

#### Scenario: Solo admin

- **WHEN** una secretaria o un odontólogo llaman `POST /admin/usuarios`
- **THEN** responde `403`

### Requirement: Edición y reactivación de usuario por admin

El sistema SHALL exponer `PATCH /admin/usuarios/:id`, solo para `admin`, que admite cambiar
`nombre`, `rol`, `activo` (para reactivar) y `password`. Un campo ausente no cambia. SHALL
responder `404` si el usuario no existe. Desactivar sigue siendo `PATCH
/admin/usuarios/:id/desactivar`.

#### Scenario: Reactivar un usuario

- **WHEN** un admin envía `activo=true` a un usuario desactivado
- **THEN** responde `200` con `activo=true` y el usuario puede volver a iniciar sesión

#### Scenario: Cambiar el rol de un usuario no admin

- **WHEN** un admin cambia el rol de una secretaria a `odontologo`
- **THEN** responde `200` y las siguientes llamadas de ese usuario se autorizan con el rol nuevo

#### Scenario: Nueva contraseña

- **WHEN** un admin envía una contraseña nueva válida
- **THEN** la contraseña anterior deja de servir para iniciar sesión y la nueva sí

### Requirement: Pantalla de gestión de usuarios

El panel admin SHALL listar los usuarios con nombre, email, rol y estado, y SHALL permitir
crear, cambiar rol, desactivar y reactivar. Ante un `409` del resguardo del último admin SHALL
mostrar el motivo devuelto por el backend y dejar la lista sin cambios. Solo `admin` SHALL ver
la pantalla.

#### Scenario: Resguardo visible en la UI

- **WHEN** el único admin activo intenta desactivarse desde la pantalla
- **THEN** la pantalla muestra el motivo del `409` y el usuario sigue activo en la lista

#### Scenario: Otro rol no ve la pantalla

- **WHEN** una secretaria navega al panel admin
- **THEN** ve "sin permiso"
