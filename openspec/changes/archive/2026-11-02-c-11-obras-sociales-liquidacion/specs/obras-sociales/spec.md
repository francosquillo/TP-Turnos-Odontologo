# Delta — obras-sociales

## ADDED Requirements

### Requirement: Catálogo de obras sociales y planes

El sistema SHALL permitir a `admin` crear, editar y desactivar obras sociales en
`/obras-sociales` y planes en `/planes`. No SHALL existir borrado físico: la baja SHALL ser
`activa: false` o `activo: false`. Todo usuario autenticado del personal SHALL poder leerlos.
Un plan SHALL pertenecer a una sola obra social. Los esquemas SHALL rechazar campos extra.

#### Scenario: Alta por admin

- **WHEN** un admin crea una obra social y un plan de esa obra social
- **THEN** responde `201` y ambos aparecen en sus listados

#### Scenario: Escritura sin permiso

- **WHEN** una secretaria o un odontólogo intenta crear o editar una obra social o un plan
- **THEN** responde `403` y no cambia ninguna fila

#### Scenario: Baja lógica

- **WHEN** un admin desactiva un plan
- **THEN** la fila persiste con `activo: false`, y las liquidaciones ya generadas no cambian

#### Scenario: Nombre repetido

- **WHEN** se crea un plan con el mismo nombre dentro de la misma obra social
- **THEN** responde `409`

#### Scenario: Campo extra

- **WHEN** el cuerpo incluye un campo desconocido
- **THEN** responde `422`

### Requirement: Aranceles versionados por vigencia

Un arancel SHALL tener plan, código de nomenclador, descripción, precio mayor a cero,
`vigencia_desde` y `vigencia_hasta` opcional. Dos aranceles del mismo plan y código SHALL NOT
superponer sus vigencias, y la base de datos SHALL garantizarlo. El precio SHALL ser
inmutable: un precio nuevo SHALL ser un arancel nuevo. Lo único editable SHALL ser
`vigencia_hasta`. Cada arancel SHALL registrar quién lo creó y quién cerró su vigencia, con
fecha (RN-GL-02). `admin` SHALL ser el único que escribe.

#### Scenario: Nueva versión

- **WHEN** un admin cierra un arancel al 30/09/2026 y crea otro desde el 01/10/2026
- **THEN** ambos conviven y cada fecha tiene un único arancel vigente

#### Scenario: Vigencias superpuestas

- **WHEN** se crea un arancel cuya vigencia se superpone con otro del mismo plan y código
- **THEN** responde `409` y no se crea la fila

#### Scenario: La base de datos impide la superposición

- **WHEN** se inserta directamente un arancel superpuesto
- **THEN** la DB lo rechaza por constraint de exclusión

#### Scenario: Precio inmutable

- **WHEN** se intenta cambiar el `precio` de un arancel existente
- **THEN** responde `422`

#### Scenario: Rango inválido

- **WHEN** `vigencia_hasta` es anterior a `vigencia_desde`
- **THEN** responde `422`

### Requirement: Validador de cobertura

`GET /validador-cobertura?paciente_id&tratamiento_id` SHALL devolver, sin crear filas, el
estado de cobertura del tratamiento para el plan actual del paciente, con el arancel vigente
en el día operativo de hoy: precio, monto cubierto, monto a cargo y porcentaje cubierto. El
monto cubierto SHALL ser el menor entre el arancel y el precio. El estado SHALL ser
`cubierto`, `sin_arancel` o `sin_plan`. Lo permiten `secretaria` y `admin`.

#### Scenario: Cobertura parcial

- **WHEN** el tratamiento cuesta 18000.00 y el arancel vigente es 12600.00
- **THEN** responde `cubierto` con `"12600.00"` cubierto, `"5400.00"` a cargo y `"70.00"` por ciento

#### Scenario: Arancel mayor al precio

- **WHEN** el arancel vigente es mayor que el precio del tratamiento
- **THEN** el monto cubierto es el precio, a cargo `"0.00"` y porcentaje `"100.00"`

#### Scenario: Usa el arancel vigente

- **WHEN** existen dos versiones del arancel y hoy corresponde a la segunda
- **THEN** responde con el importe de la segunda

#### Scenario: Paciente sin plan

- **WHEN** el paciente no tiene plan, o su plan o su obra social están inactivos
- **THEN** responde `sin_plan`, con todo el precio a cargo

#### Scenario: Sin arancel

- **WHEN** no hay arancel vigente, o el tratamiento no tiene código de nomenclador
- **THEN** responde `sin_arancel`, con todo el precio a cargo

#### Scenario: Paciente o tratamiento inexistente

- **WHEN** el paciente o el tratamiento no existen, o el paciente está dado de baja
- **THEN** responde `404`

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo consulta el validador
- **THEN** responde `403`

### Requirement: Panel de cobertura

La cuenta corriente del paciente SHALL mostrar a `secretaria` y `admin` el plan del paciente,
permitir cambiarlo y consultar la cobertura de un tratamiento. Los importes SHALL provenir del
servidor.

#### Scenario: Consulta antes del cobro

- **WHEN** una secretaria elige un tratamiento en la cuenta del paciente
- **THEN** ve el monto cubierto, el monto a cargo y el porcentaje

#### Scenario: Cambio de plan

- **WHEN** una secretaria asigna un plan
- **THEN** el panel lo muestra y las consultas siguientes lo usan
