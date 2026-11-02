# Spec Delta — datos-import-export

## Purpose

Permite migrar pacientes desde planillas y llevarse todos los datos del consultorio en un
archivo descargable, para evitar el lock-in (US-051, RN-GL-01).

## ADDED Requirements

### Requirement: Importación de pacientes con reporte por fila

El sistema SHALL exponer `POST /pacientes/import` para `admin` y `secretaria`, que recibe un
archivo CSV (UTF-8) o XLSX con las columnas `nombre`, `apellido`, `dni`, `telefono` y `email`.
SHALL validar cada fila por separado: crear las válidas y devolver, por cada fila inválida, su
número de fila en el archivo y el motivo. SHALL tratar como inválidas las filas sin nombre o
apellido, con DNI ya existente entre los pacientes activos o repetido dentro del mismo archivo,
o con teléfono o email mal formados; el teléfono se normaliza como en la reserva online. SHALL
rechazar el archivo completo con `422`, sin crear nada, si el formato no es CSV ni XLSX, si
faltan columnas obligatorias o si supera el límite de tamaño o de filas. La respuesta SHALL
informar cuántas filas se crearon y cuántas se rechazaron.

#### Scenario: Archivo con filas buenas y malas

- **WHEN** se importa un CSV con 3 filas válidas, una sin apellido y una con DNI repetido
- **THEN** se crean los 3 pacientes y el reporte lista las 2 filas rechazadas con su número y motivo

#### Scenario: DNI ya existente

- **WHEN** una fila trae el DNI de un paciente activo existente
- **THEN** esa fila se rechaza y el paciente existente no cambia

#### Scenario: XLSX equivalente

- **WHEN** se importa un XLSX con las mismas filas que un CSV válido
- **THEN** el resultado es el mismo que con el CSV

#### Scenario: Archivo sin columnas obligatorias

- **WHEN** el archivo no tiene la columna `apellido`
- **THEN** responde `422` y no se crea ningún paciente

#### Scenario: Rol sin permiso

- **WHEN** un odontólogo llama `POST /pacientes/import`
- **THEN** responde `403`

### Requirement: Exportación total descargable

El sistema SHALL exponer `GET /admin/export-total`, solo para `admin`, que devuelve un ZIP con
un CSV por tabla de negocio y un archivo que declara que los datos son ficticios. El ZIP NUNCA
SHALL incluir hashes de contraseñas, tokens ni secretos. Las celdas que una planilla podría
ejecutar como fórmula SHALL neutralizarse como en la exportación de liquidaciones.

#### Scenario: Admin descarga el ZIP

- **WHEN** un admin llama `GET /admin/export-total`
- **THEN** recibe un ZIP con un CSV de pacientes, turnos, presupuestos, movimientos, recibos y cajas, cuyas filas coinciden con la base

#### Scenario: Sin secretos

- **WHEN** se abre el CSV de usuarios del ZIP
- **THEN** no tiene columna de hash de contraseña

#### Scenario: Otro rol

- **WHEN** una secretaria llama `GET /admin/export-total`
- **THEN** responde `403`
