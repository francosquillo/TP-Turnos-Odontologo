# Spec Delta — caja

## Purpose

Permitir a la secretaria cobrar deuda de cuenta corriente con medios simulados y rendir
cada día con un cierre obligatorio y una diferencia declarada (US-031; RN-CO-01, RN-CO-02).

## ADDED Requirements

### Requirement: Una caja por día operativo

El sistema SHALL mantener como máximo una caja por fecha, y como máximo una caja abierta
en total. La fecha SHALL ser el día calendario en `America/Argentina/Buenos_Aires`,
calculado por el servidor.

#### Scenario: Fecha duplicada

- **WHEN** se inserta directamente una segunda caja con la misma fecha
- **THEN** la DB la rechaza por UNIQUE

#### Scenario: Segunda caja abierta

- **WHEN** se inserta directamente una caja abierta mientras existe otra abierta
- **THEN** la DB la rechaza por UNIQUE

#### Scenario: Antes de la medianoche local

- **WHEN** se cobra a las 23:59:59 de Buenos Aires del 30/10, que en UTC ya es 31/10
- **THEN** el cobro cae en la caja del 30/10

#### Scenario: Después de la medianoche local

- **WHEN** se cobra a las 00:00:00 de Buenos Aires del 31/10, con la caja del 30/10 cerrada
- **THEN** el cobro cae en la caja del 31/10

#### Scenario: Fecha no enviada por el cliente

- **WHEN** el cuerpo de `POST /caja/cobrar` incluye `fecha`
- **THEN** responde `422`

### Requirement: Apertura al primer movimiento

La caja del día SHALL abrirse sola con el primer movimiento y registrar quién lo generó
en `abierta_por`. No SHALL existir una operación de apertura. Consultar SHALL NOT crear
filas. Un día sin movimientos SHALL NOT tener caja ni requerir cierre.

#### Scenario: Primer cobro abre la caja

- **WHEN** una secretaria hace el primer cobro del día
- **THEN** existe una caja `abierta` con esa fecha y `abierta_por` igual a esa secretaria

#### Scenario: Primer cobro concurrente

- **WHEN** dos sesiones hacen el primer cobro del día a la vez
- **THEN** ambas responden `201` y existe una sola caja con dos movimientos

#### Scenario: Consultar no abre

- **WHEN** se hace `GET /caja` en un día sin movimientos
- **THEN** responde `200` con `caja` nula y no se crea ninguna fila

#### Scenario: Día sin movimientos

- **WHEN** ayer no hubo movimientos y hoy se cobra
- **THEN** el cobro se registra sin exigir ningún cierre de ayer

### Requirement: Cobro atómico

`POST /caja/cobrar` SHALL recibir `presupuesto_id`, `monto`, `medio` y `clave_idempotencia`,
y SHALL crear en una sola transacción el recibo, el `pago` en la cuenta corriente y el movimiento de caja.
Si algo falla, SHALL NOT quedar ninguna de las tres filas.

#### Scenario: Cobro exitoso

- **WHEN** una secretaria cobra 400.00 en `efectivo` de un presupuesto con 1000.00 pendientes
- **THEN** responde `201` con el recibo, y el saldo del paciente baja 400.00

#### Scenario: Las tres filas enlazadas

- **WHEN** se completa un cobro
- **THEN** el `pago` y el movimiento de caja referencian el mismo recibo, y el `pago`
  referencia el presupuesto

#### Scenario: Falla a mitad del cobro

- **WHEN** falla la creación del movimiento de caja
- **THEN** no queda recibo ni `pago`, y el número no se consume

#### Scenario: Presupuesto inexistente

- **WHEN** `presupuesto_id` no existe o está dado de baja
- **THEN** responde `404` y no se crea ninguna fila

#### Scenario: Paciente dado de baja con deuda

- **WHEN** se cobra un presupuesto `aceptado` de un paciente dado de baja
- **THEN** responde `201`, porque la deuda se conserva

### Requirement: Cobro idempotente

Cada intento de cobro SHALL llevar una `clave_idempotencia` UUID v4 en minúsculas, generada
por el cliente y única en la DB. La misma clave con igual contenido SHALL responder `200` con
el recibo original, sin filas ni número nuevos, también con la caja cerrada o bloqueada,
porque no mueve caja. Con otro contenido SHALL responder `409`. Un cobro rechazado o revertido
SHALL NOT retener su clave.

#### Scenario: Reintento con el mismo contenido

- **WHEN** un cobro respondió `201` y se repite con la misma clave y el mismo contenido
- **THEN** responde `200` con el recibo original, y el saldo y la caja no cambian

#### Scenario: Reintento no consume número

- **WHEN** después de un reintento se hace un cobro nuevo
- **THEN** su número es el siguiente al del recibo original

#### Scenario: Monto equivalente

- **WHEN** el cobro se hizo por `400.00` y se reintenta con `400`
- **THEN** se trata como reintento y responde `200`

#### Scenario: Misma clave con otro contenido

- **WHEN** se repite una clave con otro presupuesto, monto o medio
- **THEN** responde `409` y no se crea ninguna fila ni se consume número

#### Scenario: Clave faltante o mal formada

- **WHEN** el cuerpo no incluye la clave, o no es un UUID v4 en minúsculas
- **THEN** responde `422`

#### Scenario: Otra clave es otro cobro

- **WHEN** se envía el mismo contenido con otra clave y el pendiente alcanza
- **THEN** responde `201` con un recibo nuevo

#### Scenario: Cobro rechazado no retiene la clave

- **WHEN** un cobro responde `422` por sobrepago y se reenvía con la misma clave y un monto válido
- **THEN** responde `201`

#### Scenario: Misma clave en paralelo

- **WHEN** dos sesiones envían a la vez la misma clave y el mismo contenido
- **THEN** una responde `201` y la otra `200`, con un solo recibo, un `pago`, un movimiento
  de caja y un número consumido

#### Scenario: Misma clave en paralelo y el primero falla

- **WHEN** dos sesiones envían la misma clave y la primera se revierte
- **THEN** la segunda cobra normalmente y responde `201`

#### Scenario: Cierre mientras un reintento espera

- **WHEN** un reintento espera la caja, el cobro original confirma y luego se cierra la caja
- **THEN** responde `200` con el recibo original, no `409`

#### Scenario: Reintento con la caja del recibo cerrada

- **WHEN** se reintenta un cobro cuya caja ya se cerró
- **THEN** responde `200` con el recibo original y la caja no cambia

#### Scenario: Reintento con caja bloqueada

- **WHEN** se reintenta un cobro con una caja pendiente, o con la caja de hoy cerrada
- **THEN** responde `200` con el recibo original y no se crea ninguna caja

#### Scenario: Reintento de un recibo anulado

- **WHEN** se reintenta un cobro cuyo recibo fue anulado
- **THEN** responde `200` con `anulado: true`, sin cobrar ni revertir de nuevo

#### Scenario: Reintento sin permiso

- **WHEN** un admin envía una clave existente
- **THEN** responde `403` y no revela el recibo

#### Scenario: Clave duplicada en la DB

- **WHEN** se inserta directamente un recibo con una clave existente
- **THEN** la DB lo rechaza por UNIQUE

#### Scenario: Formato inválido en la DB

- **WHEN** se inserta directamente un recibo con una clave que no es un UUID v4 en minúsculas
- **THEN** la DB lo rechaza por CHECK

#### Scenario: Colisión de la red de seguridad

- **WHEN** la UNIQUE rechaza la clave durante un cobro
- **THEN** responde `409`, se revierte todo y el número no se consume

#### Scenario: Clave fuera de las respuestas

- **WHEN** se obtiene un recibo por cualquier ruta
- **THEN** la respuesta no incluye `clave_idempotencia`

#### Scenario: Reintento desde la pantalla

- **WHEN** un cobro falla sin respuesta o con `5xx`
- **THEN** el formulario congela importe y medio y permite reintentar con la misma clave, o
  cerrar y refrescar la cuenta

#### Scenario: Formulario nuevo

- **WHEN** se abre otra vez el formulario de cobro
- **THEN** usa una clave nueva

### Requirement: Medios simulados

Los medios SHALL ser exactamente `efectivo`, `transferencia` y `tarjeta_simulada`. El
sistema SHALL NOT contactar ningún servicio de pago. Un recibo SHALL tener un solo medio.

#### Scenario: Medio aceptado

- **WHEN** se cobra con cada uno de los tres medios
- **THEN** responde `201` con ese medio en el recibo

#### Scenario: Medio real rechazado por API

- **WHEN** se cobra con `tarjeta` o `mercadopago`
- **THEN** responde `422`

#### Scenario: Medio rechazado por la DB

- **WHEN** se inserta directamente un movimiento de caja con medio `tarjeta`
- **THEN** la DB lo rechaza por CHECK

### Requirement: Imputación a un presupuesto sin sobrepago

Un cobro SHALL imputarse a un presupuesto `aceptado`, por un monto positivo de dos
decimales y hasta su pendiente. El pendiente SHALL ser la suma de los movimientos de ese
presupuesto. Se SHALL admitir más de un cobro parcial.

#### Scenario: Cobro parcial

- **WHEN** se cobran 400.00 de un presupuesto de 1000.00
- **THEN** el presupuesto sigue `aceptado` con pendiente 600.00

#### Scenario: Sobrepago

- **WHEN** se intenta cobrar 600.01 con pendiente 600.00
- **THEN** responde `422` y no se crea ninguna fila

#### Scenario: Sobrepago concurrente

- **WHEN** dos sesiones cobran a la vez 600.00 cada una con pendiente 600.00
- **THEN** una responde `201`, la otra `409` (el ganador deja el presupuesto `cobrado`), y el pendiente queda en 0.00

#### Scenario: Monto inválido

- **WHEN** `monto` es 0, negativo o tiene más de dos decimales
- **THEN** responde `422`

#### Scenario: Presupuesto no aceptado

- **WHEN** se cobra un presupuesto `borrador`, `presentado`, `rechazado` o `cobrado`
- **THEN** responde `409`

#### Scenario: Cargo anulado

- **WHEN** se cobra un presupuesto `aceptado` con el cargo anulado
- **THEN** responde `409`, porque no tiene pendiente

### Requirement: Bloqueo por caja pendiente

Mientras exista una caja abierta de una fecha anterior, `POST /caja/cobrar` y
`POST /recibos/:id/anular` SHALL responder `409` sin crear filas. El bloqueo SHALL
aplicar solo a operaciones que mueven caja.

#### Scenario: Cobro bloqueado

- **WHEN** quedó abierta la caja de ayer y hoy se intenta cobrar
- **THEN** responde `409` y no se crea caja, recibo ni movimiento

#### Scenario: Se desbloquea al cerrar

- **WHEN** se cierra la caja de ayer y se vuelve a cobrar
- **THEN** responde `201` en la caja de hoy

#### Scenario: Agenda no bloqueada

- **WHEN** hay una caja pendiente y se crea un turno
- **THEN** la operación responde como siempre

#### Scenario: Aceptar presupuesto no bloqueado

- **WHEN** hay una caja pendiente y un odontólogo acepta un presupuesto
- **THEN** responde `200` y genera el cargo

#### Scenario: Anular un cargo no bloqueado

- **WHEN** hay una caja pendiente y un admin anula un cargo por la ruta de cuenta corriente
- **THEN** responde `201`

### Requirement: Cierre de caja

`POST /caja/cierre` SHALL recibir `caja_id` y `total_contado`, calcular `total_sistema`
como la suma de los movimientos de esa caja, guardar `diferencia = total_contado -
total_sistema`, y dejar la caja `cerrada` con autor y fecha de cierre.

#### Scenario: Cierre sin diferencia

- **WHEN** el sistema suma 1500.00 y se declaran 1500.00
- **THEN** responde `200` con `diferencia` `"0.00"` y la caja `cerrada`

#### Scenario: Total calculado por el servidor

- **WHEN** el cuerpo incluye `total_sistema` o `diferencia`
- **THEN** responde `422`

#### Scenario: Suma con anulación

- **WHEN** la caja tiene ingresos por 1000.00 y una reversión de -200.00
- **THEN** `total_sistema` es `"800.00"`

#### Scenario: Cierre de un día anterior

- **WHEN** hoy se cierra la caja abierta de ayer
- **THEN** responde `200`, y la caja conserva la fecha de ayer y registra la hora real de cierre

#### Scenario: Cierre repetido

- **WHEN** se cierra una caja ya cerrada
- **THEN** responde `409`

#### Scenario: Cierre concurrente

- **WHEN** dos sesiones cierran la misma caja a la vez
- **THEN** una responde `200`, la otra `409`

#### Scenario: Caja inexistente

- **WHEN** `caja_id` no existe
- **THEN** responde `404`

#### Scenario: Contado negativo

- **WHEN** `total_contado` es negativo
- **THEN** responde `422`

### Requirement: Diferencia declarada

Si `total_contado` difiere de `total_sistema`, el cierre SHALL exigir `motivo_diferencia`.
Sin motivo SHALL responder `422` y la caja SHALL seguir abierta. La DB SHALL rechazar una
caja cerrada con diferencia y sin motivo.

#### Scenario: Diferencia sin motivo

- **WHEN** se declaran 1400.00 contra 1500.00 sin motivo
- **THEN** responde `422` y la caja sigue `abierta`

#### Scenario: Diferencia con motivo

- **WHEN** se declaran 1400.00 contra 1500.00 con motivo
- **THEN** responde `200` con `diferencia` `"-100.00"` y el motivo guardado

#### Scenario: Sobrante

- **WHEN** se declaran 1600.00 contra 1500.00 con motivo
- **THEN** responde `200` con `diferencia` `"100.00"`

#### Scenario: Garantía en la DB

- **WHEN** se escribe directamente una caja `cerrada` con diferencia y sin motivo
- **THEN** la DB la rechaza por CHECK

### Requirement: Caja cerrada inmutable

Una caja cerrada SHALL NOT poder modificarse, reabrirse ni recibir movimientos, tampoco
por SQL directo. Ninguna caja SHALL poder borrarse. Los movimientos de caja SHALL NOT
poder modificarse ni borrarse.

#### Scenario: Cobro después del cierre del día

- **WHEN** ya se cerró la caja de hoy y se intenta cobrar
- **THEN** responde `409`

#### Scenario: UPDATE de caja cerrada

- **WHEN** se ejecuta `UPDATE` directo sobre una caja cerrada
- **THEN** la DB lo rechaza

#### Scenario: DELETE de caja

- **WHEN** se ejecuta `DELETE` directo sobre una caja
- **THEN** la DB lo rechaza

#### Scenario: Movimiento en caja cerrada

- **WHEN** se inserta directamente un movimiento en una caja cerrada
- **THEN** la DB lo rechaza

#### Scenario: Movimiento de caja inmutable

- **WHEN** se ejecuta `UPDATE` o `DELETE` directo sobre un movimiento de caja
- **THEN** la DB lo rechaza

#### Scenario: Cobro y cierre simultáneos

- **WHEN** un cobro y el cierre de la misma caja corren a la vez
- **THEN** si gana el cobro, `total_sistema` lo incluye; si gana el cierre, el cobro
  responde `409` y no deja filas

### Requirement: Consulta de la caja

`GET /caja` SHALL devolver, para hoy o para `fecha`, la caja, su desglose por medio y si
se puede operar. Sin `fecha` y con una caja pendiente, SHALL devolver esa caja y el
bloqueo. Consultar SHALL NOT crear filas.

#### Scenario: Caja del día con desglose

- **WHEN** hoy hubo cobros en efectivo y transferencia
- **THEN** responde `200` con el total del sistema y el subtotal de cada medio

#### Scenario: Caja pendiente

- **WHEN** quedó abierta la caja de ayer
- **THEN** responde con `operable: false`, `bloqueo: "caja_pendiente"` y esa caja

#### Scenario: Caja de hoy cerrada

- **WHEN** ya se cerró la caja de hoy
- **THEN** responde con `operable: false` y `bloqueo: "caja_cerrada"`

#### Scenario: Consulta de un día cerrado

- **WHEN** se consulta `fecha` de un día cerrado
- **THEN** responde con sus totales, diferencia y motivo

#### Scenario: Día sin caja

- **WHEN** se consulta `fecha` de un día sin movimientos
- **THEN** responde `200` con `caja` nula

### Requirement: Permisos sobre la caja

`POST /caja/cobrar` y `POST /caja/cierre` SHALL permitirse solo a `secretaria`.
`GET /caja` SHALL permitirse a `secretaria` y `admin`. `odontologo` SHALL NOT acceder.
Sin Bearer válido SHALL responder `401`.

#### Scenario: Admin no cobra

- **WHEN** un admin hace `POST /caja/cobrar`
- **THEN** responde `403` y no se crea ninguna fila

#### Scenario: Admin no cierra

- **WHEN** un admin hace `POST /caja/cierre`
- **THEN** responde `403` y la caja sigue abierta

#### Scenario: Admin consulta

- **WHEN** un admin hace `GET /caja`
- **THEN** responde `200`

#### Scenario: Odontólogo sin acceso

- **WHEN** un odontólogo llama a cualquier ruta de `/caja`
- **THEN** responde `403`

#### Scenario: Sin autenticación

- **WHEN** se llama a `/caja` sin Bearer
- **THEN** responde `401`

### Requirement: Sin datos clínicos en caja

Los motivos de cierre SHALL viajar en el cuerpo y SHALL NOT escribirse en logs. Los
mensajes de error SHALL ser fijos y sin datos del paciente.

#### Scenario: Motivo fuera de los logs

- **WHEN** se cierra con un texto marcador en `motivo_diferencia`
- **THEN** ningún registro de log capturado contiene ese texto

#### Scenario: Frontend sin consola

- **WHEN** se revisa el código de `features/caja`
- **THEN** no contiene llamadas a `console`

### Requirement: Pantalla de caja

`features/caja` SHALL mostrar a `secretaria` y `admin` el estado de la caja, sus totales
por medio y los recibos del día. Solo `secretaria` SHALL ver el cierre. Los importes y la
fecha operativa SHALL provenir del servidor.

#### Scenario: Acceso desde la navegación

- **WHEN** una secretaria o un admin abre Caja
- **THEN** ve la fecha operativa, el estado, el total del sistema y el desglose por medio

#### Scenario: Odontólogo sin pantalla

- **WHEN** un odontólogo intenta abrir Caja
- **THEN** no accede a la pantalla

#### Scenario: Bloqueo visible

- **WHEN** hay una caja pendiente
- **THEN** la pantalla indica con texto la fecha pendiente y que debe cerrarse para operar

#### Scenario: Cierre con diferencia

- **WHEN** el servidor rechaza un cierre por diferencia sin motivo
- **THEN** el formulario pide el motivo sin perder el importe cargado

#### Scenario: Cerrada sin acciones

- **WHEN** la caja de hoy está cerrada
- **THEN** la pantalla muestra contado y diferencia, sin acción de cierre

#### Scenario: Fecha sin corrimiento

- **WHEN** la pantalla muestra una `fecha` `2026-10-31` en un navegador en UTC-3
- **THEN** muestra 31/10/2026, no el día anterior
