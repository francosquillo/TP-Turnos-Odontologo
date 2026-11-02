# liquidaciones Specification

## Purpose
Generación, presentación, cobro a cargo de la obra social y exportación de liquidaciones por obra social y período (RN-OS-01..03, Flujo 5), con cierre de caja simulada sobre los cobros liquidados.

## Requirements

### Requirement: Generación por obra social y período

`POST /liquidaciones` SHALL recibir `os_id` y `periodo` (`YYYY-MM`) y crear una liquidación en
`borrador` con las prestaciones del período todavía no liquidadas. Una prestación SHALL ser un
ítem de un presupuesto `aceptado` o `cobrado`, con plan de esa obra social y cargo sin anular.
Su fecha SHALL ser el día operativo de la aceptación. El servidor SHALL calcular el total como
la suma de los montos. La cobertura y el arancel de cada fila SHALL ser los congelados al
aceptar. Un período MAY tener más de una liquidación.

#### Scenario: Liquidación del período

- **WHEN** un admin genera octubre para una OS con prestaciones de dos planes
- **THEN** responde `201` en `borrador`, con las filas agrupadas por plan y el total calculado

#### Scenario: Borde del período en Buenos Aires

- **WHEN** un presupuesto se acepta el 31/10 a las 23:30 en Buenos Aires
- **THEN** la prestación pertenece a octubre, aunque en UTC ya sea noviembre

#### Scenario: Arancel vigente a la fecha de prestación

- **WHEN** el arancel cambió después de aceptar el presupuesto
- **THEN** la fila usa el arancel vigente en la fecha de la prestación

#### Scenario: Cambio de plan posterior

- **WHEN** el paciente cambió de plan después de aceptar
- **THEN** la fila conserva el plan con el que se aceptó

#### Scenario: Cargo anulado

- **WHEN** el cargo del presupuesto fue anulado antes de generar
- **THEN** sus ítems no aparecen

#### Scenario: Paciente sin plan

- **WHEN** el presupuesto se aceptó sin plan
- **THEN** sus ítems no aparecen en ninguna liquidación

#### Scenario: Prestación ya liquidada

- **WHEN** se genera otra vez el mismo período sin prestaciones nuevas
- **THEN** responde `409` y no se crea ninguna fila

#### Scenario: Prestación nueva en un período ya liquidado

- **WHEN** aparece una prestación después de presentar ese período
- **THEN** una nueva generación crea otra liquidación solo con esa prestación

#### Scenario: Doble generación concurrente

- **WHEN** dos sesiones generan el mismo período a la vez
- **THEN** cada prestación queda en una sola liquidación, y la sesión que colisiona responde `409`

#### Scenario: La base de datos impide liquidar dos veces

- **WHEN** se inserta directamente otra fila con la misma prestación
- **THEN** la DB la rechaza por UNIQUE

#### Scenario: Período inválido

- **WHEN** `periodo` no es un mes `YYYY-MM` válido
- **THEN** responde `422`

### Requirement: Prestación sin arancel para revisión manual

Una prestación sin arancel al aceptar SHALL aparecer con `revision: true` y monto `0.00`. No
SHALL sumar al total, y SHALL NOT impedir presentar. Como el paciente ya la pagó completa, un
arancel creado después SHALL NOT volverla liquidable.

#### Scenario: Fila marcada

- **WHEN** el período incluye una prestación sin arancel
- **THEN** aparece con `revision: true`, y el total no la suma

#### Scenario: Arancel retroactivo

- **WHEN** se crea después un arancel para esa fecha y se regenera la liquidación
- **THEN** la fila sigue en revisión, con monto `0.00`

#### Scenario: Exportación

- **WHEN** se exporta una liquidación con filas en revisión
- **THEN** esas filas aparecen identificadas como no liquidadas

### Requirement: Estados de la liquidación

Los estados SHALL ser `borrador`, `presentada` y `cobrada`. `POST /liquidaciones/:id/presentar`
SHALL pasar de `borrador` a `presentada`. `POST /liquidaciones/:id/descartar` SHALL eliminar un
`borrador` y liberar sus prestaciones. Una liquidación presentada o cobrada SHALL NOT poder
descartarse ni editarse. Una transición inválida SHALL responder `409`.

#### Scenario: Presentar

- **WHEN** un admin presenta un `borrador`
- **THEN** queda `presentada`, con autor y fecha

#### Scenario: Presentar dos veces

- **WHEN** se presenta una liquidación ya `presentada`
- **THEN** responde `409`

#### Scenario: Descartar un borrador

- **WHEN** un admin descarta un `borrador`
- **THEN** responde `204`, y sus prestaciones vuelven a poder liquidarse

#### Scenario: Descartar presentada

- **WHEN** se descarta una liquidación `presentada` o `cobrada`
- **THEN** responde `409` y no cambia nada

#### Scenario: Sin edición de importes

- **WHEN** se buscan las rutas de la aplicación
- **THEN** ninguna permite editar el total ni los montos de una liquidación

### Requirement: Cobro de la liquidación

`POST /liquidaciones/:id/cobrar` SHALL recibir `medio` del catálogo cerrado y, en una
transacción, registrar un ingreso por el total en la caja de hoy y pasar a `cobrada`. La
liquidación SHALL cobrarse una sola vez. El monto SHALL ser siempre el total, sin cobros
parciales. Una caja pendiente o la de hoy cerrada SHALL responder `409`.

#### Scenario: Cobro

- **WHEN** un admin cobra una liquidación `presentada` de 50000.00 por transferencia
- **THEN** queda `cobrada`, y la caja de hoy suma 50000.00 en ese medio

#### Scenario: Cobrar un borrador

- **WHEN** se cobra una liquidación en `borrador`
- **THEN** responde `409` y no se crea ningún movimiento

#### Scenario: Segundo cobro

- **WHEN** se cobra otra vez una liquidación `cobrada`
- **THEN** responde `409`, y sigue habiendo un solo ingreso

#### Scenario: Cobro concurrente

- **WHEN** dos sesiones cobran la misma liquidación a la vez
- **THEN** una responde `200`, la otra `409`, y existe un solo ingreso

#### Scenario: Total en cero

- **WHEN** todas las filas de la liquidación están en revisión
- **THEN** cobrarla responde `409`

#### Scenario: Caja no operable

- **WHEN** hay una caja pendiente o la de hoy está cerrada
- **THEN** responde `409`, y la liquidación sigue `presentada`

#### Scenario: Fallo parcial

- **WHEN** falla el alta del ingreso
- **THEN** la liquidación sigue `presentada`

### Requirement: Reversión del cobro

`POST /liquidaciones/:id/revertir-cobro` SHALL exigir `motivo` y registrar un movimiento
negativo en la caja de hoy, con el medio original. Una caja cerrada SHALL NOT tocarse. La
liquidación SHALL volver a `presentada`, marcada como revertida, y SHALL NOT volver a cobrarse.

#### Scenario: Reversión

- **WHEN** un admin revierte una liquidación `cobrada` con motivo
- **THEN** la caja de hoy resta el total y la liquidación queda `presentada` y revertida

#### Scenario: Cobro de un día cerrado

- **WHEN** el ingreso está en una caja cerrada
- **THEN** esa caja no cambia y la reversión cae en la caja de hoy

#### Scenario: Sin motivo

- **WHEN** se revierte sin `motivo`
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Doble reversión

- **WHEN** se revierte una liquidación ya revertida
- **THEN** responde `409`

#### Scenario: Cobrar después de revertir

- **WHEN** se cobra una liquidación revertida
- **THEN** responde `409`

### Requirement: Exportación CSV y PDF

`GET /liquidaciones/:id/export.csv` y `GET /liquidaciones/:id/export.pdf` SHALL devolver el
informe en cualquier estado, agrupado por plan, con obra social, período, estado, filas,
subtotales y total, y la leyenda de datos ficticios. Las filas SHALL incluir paciente, fecha,
código, descripción, cantidad y monto. SHALL NOT incluir pieza dental, hallazgo ni notas
clínicas. Solo `admin` SHALL exportar.

#### Scenario: CSV

- **WHEN** un admin exporta en CSV
- **THEN** recibe un adjunto `text/csv` en UTF-8 cuyas filas y total coinciden con la liquidación

#### Scenario: Celda con fórmula

- **WHEN** el nombre de un paciente empieza con `=`, `+`, `-` o `@`
- **THEN** el CSV la escribe de modo que una planilla no la ejecute como fórmula

#### Scenario: PDF

- **WHEN** un admin exporta en PDF
- **THEN** recibe un adjunto `application/pdf` válido con los subtotales por plan y el total

#### Scenario: Exportación sin permiso

- **WHEN** un odontólogo o una secretaria exporta
- **THEN** responde `403`

### Requirement: Permisos sobre liquidaciones

`admin` SHALL tener acceso total. `odontologo` SHALL poder listar y consultar, viendo solo las
filas de sus propios presupuestos. `secretaria` SHALL NOT acceder. Sin Bearer válido SHALL
responder `401`.

#### Scenario: Odontólogo ve lo suyo

- **WHEN** un odontólogo consulta una liquidación con filas de otro profesional
- **THEN** responde `200` solo con sus filas

#### Scenario: Odontólogo no opera

- **WHEN** un odontólogo genera, presenta, descarta, cobra o revierte
- **THEN** responde `403`

#### Scenario: Secretaria sin acceso

- **WHEN** una secretaria llama a cualquier ruta de `/liquidaciones`
- **THEN** responde `403`

#### Scenario: Sin autenticación

- **WHEN** se llama a `/liquidaciones` sin Bearer
- **THEN** responde `401`

### Requirement: Sin datos sensibles en logs de liquidaciones

Los motivos SHALL viajar en el cuerpo y SHALL NOT escribirse en logs. Los errores SHALL ser
mensajes fijos y sin datos del paciente. El frontend SHALL NOT escribir en consola.

#### Scenario: Motivo fuera de los logs

- **WHEN** se revierte con un texto marcador en `motivo`
- **THEN** ningún registro de log capturado contiene ese texto

### Requirement: Pantalla de liquidaciones

`features/liquidaciones` SHALL permitir a `admin` generar por OS y período, ver las filas por
plan con las marcadas para revisión, presentar, descartar, exportar, cobrar y revertir. Un
odontólogo SHALL ver la pantalla solo de lectura. Una secretaria SHALL NOT verla.

#### Scenario: Revisión visible

- **WHEN** hay filas para revisión
- **THEN** la pantalla las indica con texto, no solo con color

#### Scenario: Caja bloqueada

- **WHEN** el servidor rechaza el cobro con `409`
- **THEN** la pantalla muestra el mensaje sin perder el medio elegido

#### Scenario: Descarga

- **WHEN** un admin exporta
- **THEN** el archivo se descarga con la sesión autenticada
