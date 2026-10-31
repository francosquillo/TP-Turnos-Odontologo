# Spec Delta — presupuestos

## Purpose

Permitir que el odontólogo arme un presupuesto desde los hallazgos del odontograma y
lo siga hasta su aceptación o rechazo, con precios congelados y permisos por rol
(US-022; RN-CL-01, RN-CL-02).

## ADDED Requirements

### Requirement: Alta de presupuesto desde hallazgos

`POST /presupuestos` SHALL crear un presupuesto en `borrador` con `paciente_id` y al
menos un ítem. El `profesional_id` SHALL derivarse del usuario autenticado y el
cliente SHALL NOT poder enviarlo, ni tampoco `estado`, `total` o `precio`.

#### Scenario: Alta válida

- **WHEN** un odontólogo vinculado al paciente envía `paciente_id` e ítems válidos
- **THEN** responde `201` con estado `borrador`, su `profesional_id` y el `total` calculado

#### Scenario: Sin ítems

- **WHEN** el cuerpo trae `items` vacío
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Campos reservados al servidor

- **WHEN** el cuerpo incluye `profesional_id`, `estado`, `total` o un ítem con `precio`
- **THEN** responde `422`

#### Scenario: Paciente inexistente o dado de baja

- **WHEN** `paciente_id` no existe o el paciente está eliminado
- **THEN** responde `404`

### Requirement: Cada ítem referencia un hallazgo y un tratamiento

Cada ítem SHALL referenciar un hallazgo activo de la historia clínica activa del
paciente y un tratamiento del catálogo, con `cantidad` entre 1 y 99. Hallazgo y
tratamiento SHALL ser obligatorios en la API y en la base de datos.

#### Scenario: Ítem sin hallazgo

- **WHEN** un ítem no incluye `hallazgo_id`
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Ítem sin tratamiento

- **WHEN** un ítem no incluye `tratamiento_id`
- **THEN** responde `422`

#### Scenario: La base de datos exige hallazgo

- **WHEN** se inserta directamente un ítem con `hallazgo_id` nulo
- **THEN** la DB lo rechaza por NOT NULL

#### Scenario: Hallazgo dado de baja

- **WHEN** el ítem referencia un hallazgo con `deleted_at`
- **THEN** responde `422`

#### Scenario: Hallazgo de otro paciente

- **WHEN** el ítem referencia un hallazgo de otro paciente
- **THEN** responde `422` con un mensaje fijo, sin datos de ese paciente

#### Scenario: Tratamiento inexistente

- **WHEN** `tratamiento_id` no existe en el catálogo
- **THEN** responde `422`

#### Scenario: Cantidad fuera de rango

- **WHEN** `cantidad` es 0 o 100
- **THEN** responde `422`

#### Scenario: Demasiados ítems

- **WHEN** el cuerpo trae más de 50 ítems
- **THEN** responde `422`

#### Scenario: Ítem repetido

- **WHEN** dos ítems repiten el mismo par hallazgo y tratamiento
- **THEN** responde `422`

### Requirement: Precio congelado por el servidor

Al guardar un ítem, el sistema SHALL copiar `Tratamiento.precio_base` en `precio`. Un
cambio posterior del catálogo SHALL NOT alterar ítems ya guardados de presupuestos
fuera de `borrador`.

#### Scenario: Copia del precio

- **WHEN** se crea un ítem de un tratamiento con `precio_base` 15000.00
- **THEN** el ítem queda con `precio` 15000.00

#### Scenario: El catálogo cambia después de presentar

- **WHEN** cambia `precio_base` de un tratamiento de un presupuesto `presentado`
- **THEN** el ítem conserva su `precio` y el presupuesto su `total`

#### Scenario: Reemplazo en borrador toma el precio vigente

- **WHEN** se reemplazan los ítems de un `borrador` después de un cambio de `precio_base`
- **THEN** los ítems nuevos toman el precio vigente

### Requirement: Total calculado por el servidor

`total` SHALL ser la suma de `cantidad × precio` de los ítems, con dos decimales, y
SHALL recalcularse en la misma transacción que modifique los ítems. Los importes
SHALL viajar como texto decimal en JSON.

#### Scenario: Suma de ítems

- **WHEN** un presupuesto tiene un ítem de 2 × 1000.50 y otro de 1 × 500.00
- **THEN** `total` es `"2501.00"`

#### Scenario: Recalcular al reemplazar

- **WHEN** se reemplazan los ítems de un `borrador`
- **THEN** `total` refleja solo los ítems nuevos

### Requirement: Máquina de estados del presupuesto

Los estados SHALL ser `borrador, presentado, aceptado, rechazado, cobrado`. Las únicas
transiciones por API de este change SHALL ser `borrador → presentado`, `presentado →
aceptado` y `presentado → rechazado`. Una transición inválida SHALL responder `409`.

#### Scenario: Presentar

- **WHEN** el autor hace `POST /presupuestos/:id/presentar` sobre un `borrador` válido
- **THEN** responde `200` con estado `presentado` y `presentado_at` del reloj del servidor

#### Scenario: Aceptar un borrador

- **WHEN** se hace `POST /presupuestos/:id/aceptar` sobre un `borrador`
- **THEN** responde `409` y no se genera ningún movimiento

#### Scenario: Reabrir un estado final

- **WHEN** se intenta presentar, aceptar o rechazar un presupuesto `aceptado` o `rechazado`
- **THEN** responde `409`

#### Scenario: Estado fuera del catálogo

- **WHEN** se escribe directamente un `estado` desconocido
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Sin camino a cobrado en este change

- **WHEN** un cliente envía `estado: "cobrado"` en `POST /presupuestos` o `PUT /presupuestos/:id`
- **THEN** responde `422`

### Requirement: Solo se presenta un presupuesto con importe

`presentar` SHALL exigir `total` mayor que cero, para que todo presupuesto aceptado
pueda generar su cargo.

#### Scenario: Total cero

- **WHEN** se presenta un `borrador` cuyos tratamientos tienen `precio_base` 0
- **THEN** responde `422` y sigue en `borrador`

### Requirement: Edición solo en borrador

`PUT /presupuestos/:id` SHALL reemplazar la lista completa de ítems y SHALL estar
permitido solo en `borrador`. Fuera de `borrador` los ítems SHALL ser inmutables.

#### Scenario: Edición de borrador

- **WHEN** el autor envía una lista nueva de ítems válidos
- **THEN** responde `200` con los ítems y el `total` nuevos

#### Scenario: Edición de presentado

- **WHEN** se hace `PUT` sobre un presupuesto `presentado`
- **THEN** responde `409` y los ítems no cambian

### Requirement: Hallazgos vigentes al presentar y al aceptar

`presentar` y `aceptar` SHALL fallar con `409` si algún ítem referencia un hallazgo
dado de baja o corregido. Una vez aceptado, una corrección del hallazgo SHALL NOT
modificar el presupuesto, que seguirá mostrando la fila original.

#### Scenario: Hallazgo corregido antes de presentar

- **WHEN** se corrige un hallazgo de un `borrador` y luego se lo presenta
- **THEN** responde `409`, sigue en `borrador` y se puede editar con el hallazgo nuevo

#### Scenario: Hallazgo dado de baja antes de aceptar

- **WHEN** se da de baja un hallazgo de un `presentado` y luego se lo acepta
- **THEN** responde `409` y no se genera ningún movimiento

#### Scenario: Corrección después de aceptar

- **WHEN** se corrige un hallazgo de un `aceptado`
- **THEN** la corrección procede, el presupuesto sigue `aceptado` y el ítem indica `hallazgo_vigente: false`

### Requirement: Aceptación con cargo automático

`aceptar` SHALL pasar el presupuesto a `aceptado` y generar en la misma transacción
un único cargo por `total` en la cuenta corriente del paciente. Si falla alguno de
los dos pasos, ninguno SHALL persistir.

#### Scenario: Aceptación

- **WHEN** el autor acepta un `presentado` de total 2501.00
- **THEN** responde `200` con estado `aceptado` y la cuenta tiene un cargo de 2501.00 con ese `presupuesto_id`

#### Scenario: Doble aceptación secuencial

- **WHEN** se repite `aceptar` sobre un presupuesto ya `aceptado`
- **THEN** responde `409` y sigue habiendo un solo cargo

#### Scenario: Doble aceptación concurrente

- **WHEN** dos sesiones aceptan el mismo presupuesto al mismo tiempo
- **THEN** una responde `200`, la otra `409` y existe un solo cargo

#### Scenario: La base de datos impide un segundo cargo

- **WHEN** se inserta directamente un segundo `cargo` con el mismo `presupuesto_id`
- **THEN** la DB lo rechaza por índice único parcial

### Requirement: Rechazo con motivo

`rechazar` SHALL exigir `motivo`, pasar a `rechazado` sin generar movimientos y
conservar el presupuesto en el historial del paciente.

#### Scenario: Rechazo

- **WHEN** el autor rechaza un `presentado` con `motivo`
- **THEN** responde `200` con estado `rechazado`, `motivo_rechazo` y sin movimientos

#### Scenario: Rechazo sin motivo

- **WHEN** se hace `rechazar` sin `motivo`
- **THEN** responde `422` y el estado no cambia

#### Scenario: La base de datos exige motivo

- **WHEN** se escribe directamente `estado='rechazado'` sin `motivo_rechazo`
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Historial para recupero

- **WHEN** se hace `GET /presupuestos?paciente_id=7&estado=rechazado`
- **THEN** devuelve los presupuestos rechazados de ese paciente

### Requirement: Baja lógica solo en borrador

`POST /presupuestos/:id/baja` SHALL dar de baja un `borrador` con motivo obligatorio,
conservando la fila. Un presupuesto de otro estado SHALL responder `409`. No SHALL
existir borrado físico por API.

#### Scenario: Baja de borrador

- **WHEN** el autor da de baja un `borrador` con `motivo_baja`
- **THEN** responde `200`, la fila conserva sus datos y después responde `404` en la API

#### Scenario: Baja de presentado

- **WHEN** se da de baja un presupuesto `presentado`
- **THEN** responde `409`

#### Scenario: La base de datos limita la baja

- **WHEN** se escribe directamente `deleted_at` en un presupuesto `aceptado`
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Sin DELETE físico

- **WHEN** se hace `DELETE /presupuestos/:id`
- **THEN** responde `405`

### Requirement: Consulta de presupuestos

`GET /presupuestos` SHALL exigir `paciente_id`, admitir `estado` y devolver del más
reciente al más antiguo, sin bajas. `GET /presupuestos/:id` SHALL devolver cabecera e
ítems con nombre de tratamiento, subtotal y `hallazgo_vigente`.

#### Scenario: Listado sin paciente

- **WHEN** se hace `GET /presupuestos` sin `paciente_id`
- **THEN** responde `422`

#### Scenario: Detalle con datos del hallazgo

- **WHEN** un odontólogo vinculado o una secretaria consulta el detalle
- **THEN** cada ítem trae `pieza_fdi`, `cara`, `tratamiento_nombre`, `cantidad`, `precio` y `subtotal`

#### Scenario: Presupuesto inexistente

- **WHEN** el `id` no existe
- **THEN** responde `404`

### Requirement: Permisos sobre presupuestos

Solo el rol `odontologo` SHALL escribir. `secretaria` y `admin` SHALL leer cualquier
presupuesto, sin escribir. Sin Bearer válido SHALL responder `401`.

#### Scenario: Secretaria lee

- **WHEN** una secretaria hace `GET /presupuestos/:id`
- **THEN** responde `200`

#### Scenario: Secretaria y admin no escriben

- **WHEN** una secretaria o un admin hace `POST`, `PUT`, `presentar`, `aceptar`, `rechazar` o `baja`
- **THEN** responde `403`

#### Scenario: Sin autenticación

- **WHEN** se llama a cualquier endpoint de `/presupuestos` sin Bearer
- **THEN** responde `401`

### Requirement: Vista financiera para admin

Para el rol `admin`, las respuestas de `/presupuestos` SHALL devolver `null` en
`pieza_fdi`, `cara` y `motivo_rechazo`, conservando importes, tratamientos y estados,
porque el admin no tiene acceso a datos clínicos.

#### Scenario: Admin consulta el detalle

- **WHEN** un admin hace `GET /presupuestos/:id`
- **THEN** responde `200` con importes y tratamientos, y `pieza_fdi`, `cara` y `motivo_rechazo` en `null`

### Requirement: Odontólogo limitado a sus pacientes y sus presupuestos

Un odontólogo SHALL acceder solo a presupuestos de pacientes con los que tenga un
turno no cancelado, y SHALL modificar, presentar, aceptar, rechazar o dar de baja solo
los propios. Debe tener un `Profesional` vinculado a su usuario.

#### Scenario: Sin vínculo

- **WHEN** consulta o crea un presupuesto de un paciente sin turnos suyos
- **THEN** responde `403`

#### Scenario: Presupuesto de otro odontólogo

- **WHEN** otro odontólogo vinculado al paciente lo consulta
- **THEN** responde `200`

#### Scenario: Escritura sobre presupuesto ajeno

- **WHEN** otro odontólogo vinculado intenta aceptarlo
- **THEN** responde `403` y nada cambia

#### Scenario: Usuario sin profesional

- **WHEN** un usuario `odontologo` sin `Profesional` vinculado crea un presupuesto
- **THEN** responde `403`

### Requirement: Sin datos clínicos en logs de presupuestos

El sistema SHALL NOT escribir en logs motivos ni datos de ítems, en backend ni en
frontend, y los mensajes de error SHALL ser fijos.

#### Scenario: Operaciones y errores

- **WHEN** se ejecutan operaciones exitosas y fallidas con textos marcadores en los motivos
- **THEN** ningún registro de log capturado contiene esos textos

#### Scenario: Frontend sin consola

- **WHEN** se revisa el código de `features/presupuestos`
- **THEN** no contiene llamadas a `console`

### Requirement: Migración reversible encadenada

La migración SHALL ser `006_presupuestos_cc` con `down_revision = 005_clinica`, con una
sola cabeza, y SHALL ser reversible.

#### Scenario: Cadena única

- **WHEN** se inspeccionan las revisiones de Alembic
- **THEN** hay una sola cabeza, `006_presupuestos_cc`, sobre `005_clinica`

#### Scenario: Reversión limpia

- **WHEN** se ejecuta `alembic downgrade 005_clinica` y luego `upgrade head`
- **THEN** ambas operaciones terminan sin error

### Requirement: Pantalla de presupuestos desde el odontograma

La pantalla de odontograma SHALL ofrecer los presupuestos del paciente. El odontólogo
SHALL poder armarlos eligiendo hallazgos activos y tratamientos, y operar sus estados;
la secretaria SHALL verlos sin controles. El estado SHALL mostrarse con texto.

#### Scenario: Armar desde hallazgos

- **WHEN** un odontólogo crea un presupuesto
- **THEN** solo puede elegir hallazgos activos del paciente, indicados por pieza y cara, y el total mostrado viene del servidor

#### Scenario: Secretaria en solo lectura

- **WHEN** una secretaria abre los presupuestos
- **THEN** ve lista y detalle sin controles de alta, edición ni cambio de estado

#### Scenario: Rechazo desde la pantalla

- **WHEN** el odontólogo rechaza sin escribir motivo
- **THEN** el formulario no se envía e indica que el motivo es obligatorio

#### Scenario: Hallazgo desactualizado

- **WHEN** la API responde `409` al presentar o aceptar
- **THEN** la pantalla muestra el mensaje y el presupuesto sigue operable

#### Scenario: Tipado estricto de importes

- **WHEN** se muestran importes
- **THEN** se formatean desde el texto decimal de la API, sin aritmética de dinero en el cliente
