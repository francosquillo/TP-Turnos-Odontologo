# clinica-odontograma-hc Specification

## Purpose
Dar al odontólogo una historia clínica por paciente y un odontograma FDI con
historial por pieza, con alergias siempre visibles y baja lógica, y dejar
hallazgos y tratamientos como contrato para los presupuestos de C-09 (US-020,
US-021; RN-CL-01, RN-CL-03, RN-CL-04, RN-GL-01).

## Requirements

### Requirement: Una historia clínica por paciente

El sistema SHALL permitir como máximo una historia clínica por paciente, con
antecedentes y alergias opcionales, y SHALL rechazar una segunda aunque la
primera esté dada de baja.

#### Scenario: Alta de historia clínica

- **WHEN** un odontólogo vinculado al paciente hace `POST /historias` con `paciente_id`
- **THEN** responde `201` con la historia, incluidas `antecedentes` y `alergias`

#### Scenario: Historia duplicada

- **WHEN** se hace `POST /historias` para un paciente que ya tiene historia activa
- **THEN** responde `409` y no se crea ninguna fila

#### Scenario: Historia dada de baja impide crear otra

- **WHEN** se hace `POST /historias` para un paciente cuya historia está dada de baja
- **THEN** responde `409` con detalle que indica que la historia está dada de baja

#### Scenario: Paciente inexistente o dado de baja

- **WHEN** se hace `POST /historias` con un paciente inexistente o eliminado
- **THEN** responde `404`

#### Scenario: Búsqueda por paciente sin historia

- **WHEN** se hace `GET /historias?paciente_id=7` y ese paciente no tiene historia activa
- **THEN** responde `200` con lista vacía

#### Scenario: Búsqueda sin paciente

- **WHEN** se hace `GET /historias` sin `paciente_id`
- **THEN** responde `422`

### Requirement: Actualización parcial de historia clínica

El sistema SHALL actualizar solo los campos enviados en `PATCH /historias/:id` y
SHALL registrar la fecha de la última modificación.

#### Scenario: Actualiza alergias sin tocar antecedentes

- **WHEN** se hace `PATCH /historias/:id` enviando solo `alergias`
- **THEN** `alergias` cambia, `antecedentes` queda igual y `updated_at` avanza

#### Scenario: Campo desconocido

- **WHEN** el cuerpo incluye un campo no declarado
- **THEN** responde `422`

### Requirement: Alergias visibles en toda respuesta clínica

Toda respuesta de `/historias` y de `/odontograma/:hc_id/hallazgos` SHALL incluir
`alergias`. El valor `null` SHALL significar "no relevadas", distinto de un texto
que declare que no tiene alergias, y un texto vacío SHALL normalizarse a `null`.

#### Scenario: Alergias en el listado de hallazgos

- **WHEN** se hace `GET /odontograma/:hc_id/hallazgos`
- **THEN** la respuesta trae `alergias` en la raíz junto a `hallazgos`

#### Scenario: Alergias al registrar un hallazgo

- **WHEN** se hace `POST /odontograma/:hc_id/hallazgos` con datos válidos
- **THEN** la respuesta trae `alergias` en la raíz junto a `hallazgo`

#### Scenario: Alergias no relevadas

- **WHEN** se envía `alergias` como texto vacío o solo espacios
- **THEN** se guarda `null` y la respuesta devuelve `alergias: null`

### Requirement: Pantalla clínica con alergias siempre a la vista

La pantalla de odontograma SHALL mostrar las alergias de forma permanente, con
texto y sin depender solo del color, y SHALL indicar expresamente cuando no
están relevadas.

#### Scenario: Paciente con alergias

- **WHEN** se abre el odontograma de un paciente con alergias cargadas
- **THEN** el aviso muestra el texto de las alergias antes de la grilla y sigue visible al abrir el detalle de una pieza

#### Scenario: Alergias no relevadas en pantalla

- **WHEN** se abre el odontograma de un paciente con `alergias: null`
- **THEN** el aviso dice que las alergias no están relevadas

### Requirement: Notación FDI de dentición permanente

El sistema SHALL aceptar como `pieza_fdi` únicamente 11–18, 21–28, 31–38 y 41–48,
y SHALL rechazar cualquier otro valor en la API y en la base de datos.

#### Scenario: Piezas válidas en los bordes de cada cuadrante

- **WHEN** se registra un hallazgo con pieza 11, 18, 21, 28, 31, 38, 41 o 48
- **THEN** el hallazgo se crea

#### Scenario: Valores dentro de 11–48 que no son piezas

- **WHEN** se envía `pieza_fdi` 19, 20, 29, 30, 39 o 40
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Valores fuera de rango y dentición temporal

- **WHEN** se envía `pieza_fdi` 10, 49, 51 u 85
- **THEN** responde `422`

#### Scenario: La base de datos rechaza una pieza inválida

- **WHEN** se inserta directamente una fila con `pieza_fdi` 19
- **THEN** la DB la rechaza por CHECK

#### Scenario: Filtro por pieza inválida

- **WHEN** se hace `GET /odontograma/:hc_id/hallazgos?pieza=30`
- **THEN** responde `422`

### Requirement: Cara obligatoria y coherente con la arcada

Todo hallazgo SHALL tener una cara del conjunto cerrado `oclusal, mesial, distal,
vestibular, palatina, lingual, raiz, pieza_completa`. `palatina` SHALL admitirse
solo en piezas superiores (1x, 2x) y `lingual` solo en inferiores (3x, 4x).

#### Scenario: Cara fuera del catálogo

- **WHEN** se envía `cara: "incisal"`
- **THEN** responde `422`

#### Scenario: Palatina en pieza inferior

- **WHEN** se envía `cara: "palatina"` con pieza 36
- **THEN** responde `422`

#### Scenario: Lingual en pieza superior

- **WHEN** se envía `cara: "lingual"` con pieza 16
- **THEN** responde `422`

#### Scenario: La base de datos rechaza la arcada incorrecta

- **WHEN** se inserta directamente una fila con `cara='lingual'` y `pieza_fdi=16`
- **THEN** la DB la rechaza por CHECK

#### Scenario: Cara omitida

- **WHEN** se registra un hallazgo sin `cara`
- **THEN** responde `422`

### Requirement: Catálogo cerrado y versionado de estados

Los estados de hallazgo SHALL provenir de un catálogo versionado que la API solo
expone para lectura. La versión 1 SHALL contener `sano, caries, obturacion,
corona, endodoncia, implante, ausente`. Cada hallazgo SHALL guardar la versión
vigente al registrarse.

#### Scenario: Consulta del catálogo vigente

- **WHEN** un usuario autenticado de cualquier rol hace `GET /odontograma/catalogo`
- **THEN** responde `200` con la versión vigente y sus estados con `codigo`, `nombre` y `alcance`

#### Scenario: Estado fuera del catálogo

- **WHEN** se envía `estado: "desconocido"`
- **THEN** responde `422`

#### Scenario: La base de datos rechaza un estado sin catálogo

- **WHEN** se inserta directamente un hallazgo con un par `estado` + `catalogo_version` inexistente
- **THEN** la DB lo rechaza por FK

#### Scenario: Estado de una versión anterior

- **WHEN** se envía un estado que solo existe en una versión no vigente
- **THEN** responde `422`

#### Scenario: Hallazgos antiguos sobreviven a una versión nueva

- **WHEN** entra en vigencia una versión 2 del catálogo
- **THEN** los hallazgos existentes conservan `catalogo_version = 1` y siguen listándose

#### Scenario: La versión no la elige el cliente

- **WHEN** el cuerpo de alta incluye `catalogo_version`
- **THEN** responde `422`

### Requirement: Estados que aplican a la pieza completa

Los estados con `alcance = pieza` (`corona, endodoncia, implante, ausente`) SHALL
registrarse con `cara = pieza_completa`. Los estados con `alcance = cualquiera`
SHALL admitir cualquier cara válida.

#### Scenario: Pieza ausente en una cara

- **WHEN** se envía `estado: "ausente"` con `cara: "mesial"`
- **THEN** responde `422`

#### Scenario: Pieza ausente completa

- **WHEN** se envía `estado: "ausente"` con `cara: "pieza_completa"`
- **THEN** el hallazgo se crea

#### Scenario: Caries en una cara

- **WHEN** se envía `estado: "caries"` con `cara: "oclusal"`
- **THEN** el hallazgo se crea

### Requirement: Autoría y fecha de un hallazgo a cargo del servidor

El sistema SHALL tomar `profesional_id` del usuario autenticado y `fecha` del
reloj del servidor. El cliente SHALL NOT poder enviarlos.

#### Scenario: Autoría derivada del token

- **WHEN** un odontólogo registra un hallazgo
- **THEN** `profesional_id` es el profesional vinculado a su usuario y `fecha` es el momento del registro

#### Scenario: Intento de fijar el autor

- **WHEN** el cuerpo incluye `profesional_id` o `fecha`
- **THEN** responde `422`

### Requirement: Corrección de hallazgos sin sobrescritura

`PUT /odontograma/:hc_id/hallazgos/:id` SHALL dar de baja la fila corregida con el
motivo recibido y crear otra que la referencie en `corrige_a_id`, en una sola
transacción. Una fila dada de baja SHALL NOT poder corregirse.

#### Scenario: Corrección conserva el original

- **WHEN** el autor corrige un hallazgo con datos válidos y `motivo`
- **THEN** responde `200` con un hallazgo de `id` nuevo y `corrige_a_id` igual al original, y el original queda con `deleted_at` y `motivo_baja`

#### Scenario: Corrección sin motivo

- **WHEN** se hace `PUT` sin `motivo`
- **THEN** responde `422` y el original no cambia

#### Scenario: Corrección de una fila ya dada de baja

- **WHEN** se hace `PUT` sobre un hallazgo dado de baja
- **THEN** responde `409`

#### Scenario: Hallazgo de otra historia

- **WHEN** el `id` del hallazgo no pertenece a `hc_id`
- **THEN** responde `404`

### Requirement: Baja lógica de hallazgos

`POST /odontograma/:hc_id/hallazgos/:id/baja` SHALL marcar el hallazgo como dado de
baja con motivo obligatorio y SHALL conservar la fila. No SHALL existir borrado
físico por API.

#### Scenario: Baja con motivo

- **WHEN** el autor da de baja un hallazgo con `motivo_baja`
- **THEN** la fila conserva sus datos, queda con `deleted_at` y deja de aparecer en el listado por defecto

#### Scenario: Baja repetida

- **WHEN** se da de baja un hallazgo que ya lo está
- **THEN** responde `409`

#### Scenario: La base de datos exige motivo

- **WHEN** se escribe directamente `deleted_at` sin `motivo_baja`
- **THEN** la DB lo rechaza por CHECK

### Requirement: Historial por pieza

`GET /odontograma/:hc_id/hallazgos` SHALL devolver los hallazgos activos del más
reciente al más antiguo, y SHALL admitir `pieza` e `incluir_anulados` para ver el
historial completo de una pieza.

#### Scenario: Historial de una pieza

- **WHEN** una pieza tiene `caries` y luego `obturacion`, y se consulta con `pieza=16`
- **THEN** devuelve ambos hallazgos con `obturacion` primero y ninguno de otras piezas

#### Scenario: Historial con anulados

- **WHEN** se consulta con `pieza=16&incluir_anulados=true`
- **THEN** incluye las filas dadas de baja con `deleted_at` y `motivo_baja`

#### Scenario: Listado por defecto

- **WHEN** se consulta sin `incluir_anulados`
- **THEN** no aparecen filas dadas de baja

### Requirement: Baja lógica de historia clínica

`POST /historias/:id/baja` SHALL dar de baja la historia con motivo obligatorio.
Una historia dada de baja SHALL responder `404` en toda la API y sus hallazgos
SHALL conservarse en la base de datos.

#### Scenario: Baja de historia

- **WHEN** un odontólogo vinculado da de baja una historia con `motivo_baja`
- **THEN** responde `200` y la fila sigue en la base con `deleted_at`

#### Scenario: Acceso posterior a la baja

- **WHEN** se consulta `GET /historias/:id` o `GET /odontograma/:hc_id/hallazgos` de esa historia
- **THEN** responde `404`

#### Scenario: Hallazgos intactos

- **WHEN** se da de baja una historia con hallazgos
- **THEN** los hallazgos siguen en la base sin modificarse

#### Scenario: Baja sin motivo

- **WHEN** se hace `POST /historias/:id/baja` sin `motivo_baja`
- **THEN** responde `422`

#### Scenario: Sin DELETE físico

- **WHEN** se hace `DELETE /historias/:id`
- **THEN** responde `405`

### Requirement: Acceso clínico por rol

El rol `secretaria` SHALL poder leer historias y hallazgos sin escribir. El rol
`admin` SHALL NOT acceder a historias ni hallazgos. El rol `odontologo` SHALL
escribir según su vínculo. Sin Bearer válido SHALL responder `401`.

#### Scenario: Secretaria lee

- **WHEN** una secretaria hace `GET /historias/:id` o lista hallazgos
- **THEN** responde `200`

#### Scenario: Secretaria no escribe

- **WHEN** una secretaria hace `POST`, `PATCH` o `PUT` sobre `/historias` u `/odontograma`
- **THEN** responde `403`

#### Scenario: Admin sin acceso a datos clínicos

- **WHEN** un admin consulta `/historias` o `/odontograma/:hc_id/hallazgos`
- **THEN** responde `403`

#### Scenario: Sin autenticación

- **WHEN** se llama a cualquier endpoint clínico sin Bearer
- **THEN** responde `401`

### Requirement: Odontólogo limitado a sus pacientes y sus hallazgos

Un odontólogo SHALL acceder solo a pacientes con los que tenga al menos un turno
no cancelado, y SHALL corregir o dar de baja solo hallazgos propios. Debe tener
un `Profesional` vinculado a su usuario.

#### Scenario: Odontólogo con turno ve la historia

- **WHEN** consulta la historia de un paciente con un turno suyo `asistido`
- **THEN** responde `200`

#### Scenario: Otro odontólogo también ve la historia compartida

- **WHEN** dos odontólogos tienen turnos con el mismo paciente y uno consulta los hallazgos del otro
- **THEN** responde `200` con todos los hallazgos del paciente

#### Scenario: Odontólogo sin vínculo

- **WHEN** consulta o escribe la historia de un paciente sin turnos suyos
- **THEN** responde `403`

#### Scenario: Solo turnos cancelados

- **WHEN** su único turno con el paciente está `cancelado`
- **THEN** responde `403`

#### Scenario: Usuario odontólogo sin profesional vinculado

- **WHEN** un usuario con rol `odontologo` y sin `Profesional` vinculado registra un hallazgo
- **THEN** responde `403`

#### Scenario: Hallazgo de otro profesional

- **WHEN** intenta corregir o dar de baja un hallazgo de otro odontólogo
- **THEN** responde `403` y la fila no cambia

### Requirement: Catálogo de tratamientos de solo lectura

`GET /tratamientos` SHALL devolver a cualquier rol autenticado el catálogo con
`id, codigo, codigo_nomenclador, nombre, precio_base`. `codigo` SHALL ser único,
`codigo_nomenclador` opcional y `precio_base` no negativo. No SHALL existir
escritura por API.

#### Scenario: Lectura del catálogo

- **WHEN** un admin, una secretaria o un odontólogo hace `GET /tratamientos`
- **THEN** responde `200` con los tratamientos ordenados por `codigo`

#### Scenario: Sin escritura por API

- **WHEN** se hace `POST /tratamientos`
- **THEN** responde `405`

#### Scenario: Código duplicado

- **WHEN** se inserta directamente un tratamiento con `codigo` repetido
- **THEN** la DB lo rechaza por UNIQUE

#### Scenario: Precio negativo

- **WHEN** se inserta directamente un tratamiento con `precio_base` negativo
- **THEN** la DB lo rechaza por CHECK

### Requirement: Identificadores estables para presupuestos

El `id` de hallazgos y tratamientos SHALL mantenerse estable y sus filas SHALL
seguir existiendo tras una baja o corrección, de modo que una referencia futura
desde un presupuesto no quede huérfana.

#### Scenario: Hallazgo corregido sigue accesible

- **WHEN** se corrige un hallazgo
- **THEN** la fila original conserva su `id` y la nueva permite llegar a ella por `corrige_a_id`

#### Scenario: Borrado físico de una historia con hallazgos

- **WHEN** se intenta borrar por SQL una historia con hallazgos
- **THEN** la DB lo rechaza por FK `RESTRICT`

### Requirement: Sin datos clínicos en logs

El sistema SHALL NOT escribir en logs antecedentes, alergias, motivos ni datos de
hallazgos, en backend ni en frontend, tampoco ante errores de validación.

#### Scenario: Operaciones clínicas exitosas

- **WHEN** se crean y actualizan historias y hallazgos con textos marcadores
- **THEN** ningún registro de log capturado contiene esos textos

#### Scenario: Error de validación

- **WHEN** una petición clínica falla con `422` y lleva textos marcadores
- **THEN** ningún registro de log capturado contiene esos textos

#### Scenario: Frontend sin registros en consola

- **WHEN** se revisa el código de `features/odontograma`
- **THEN** no contiene llamadas a `console`

### Requirement: Migración reversible encadenada

La migración SHALL ser `005_clinica` con `down_revision = 004_espera`, con una sola
cabeza, SHALL dejar cargada la versión 1 del catálogo y SHALL ser reversible.

#### Scenario: Cadena única

- **WHEN** se inspeccionan las revisiones de Alembic
- **THEN** hay una sola cabeza, `005_clinica`, y su `down_revision` es `004_espera`

#### Scenario: Catálogo disponible sin seed

- **WHEN** se ejecuta `alembic upgrade head` sobre una base limpia
- **THEN** existen los 7 estados de la versión 1, sin correr el seed

#### Scenario: Índice de historial

- **WHEN** se inspecciona `hallazgo_odontograma`
- **THEN** existe un índice sobre `(hc_id, pieza_fdi)`

#### Scenario: Reversión limpia

- **WHEN** se ejecuta `alembic downgrade -1` y luego `upgrade head`
- **THEN** ambas operaciones terminan sin error

### Requirement: Seed clínico demo idempotente

El seed SHALL crear tratamientos ficticios y usuarios demo `odontologo` (vinculado
al profesional demo si no tenía usuario) y `secretaria`, sin secretos en código y
sin duplicar nada al repetirse.

#### Scenario: Doble ejecución

- **WHEN** se ejecuta el seed dos veces
- **THEN** los conteos de tratamientos y usuarios no cambian

#### Scenario: Vínculo del odontólogo demo

- **WHEN** se ejecuta el seed sobre el profesional demo sin usuario
- **THEN** el profesional queda vinculado al usuario `odontologo` demo

#### Scenario: Vínculo existente se respeta

- **WHEN** el profesional demo ya tiene otro usuario vinculado
- **THEN** el seed no cambia ese vínculo

### Requirement: Grilla de odontograma

`features/odontograma` SHALL mostrar las 32 piezas por cuadrante en orden clínico,
el estado vigente con texto, el historial al elegir una pieza y controles de carga
solo para el rol `odontologo`.

#### Scenario: Orden de la grilla

- **WHEN** se abre el odontograma
- **THEN** la fila superior va de 18 a 11 y de 21 a 28, y la inferior de 48 a 41 y de 31 a 38, sin 19, 20, 29, 30, 39 ni 40

#### Scenario: Estado vigente por cara

- **WHEN** una cara tiene varios hallazgos activos
- **THEN** la grilla muestra el más reciente con su nombre en texto

#### Scenario: Historial de la pieza

- **WHEN** se elige una pieza
- **THEN** se ve su historial, incluidas las filas dadas de baja con motivo

#### Scenario: Secretaria en solo lectura

- **WHEN** una secretaria abre el odontograma
- **THEN** ve la grilla y el historial sin controles de alta, corrección ni baja

#### Scenario: Caras válidas según pieza y estado

- **WHEN** el odontólogo carga un hallazgo en una pieza inferior o con estado `ausente`
- **THEN** el formulario no ofrece `palatina` y, con `ausente`, solo ofrece `pieza_completa`

#### Scenario: Paciente sin historia

- **WHEN** un odontólogo abre un paciente sin historia
- **THEN** se le ofrece abrir la historia; una secretaria ve un mensaje de que no existe

#### Scenario: Acceso desde la agenda

- **WHEN** un odontólogo o una secretaria ve un turno en la agenda
- **THEN** tiene un acceso al odontograma de ese paciente; un admin no lo ve
