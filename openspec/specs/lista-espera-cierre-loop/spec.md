# lista-espera-cierre-loop Specification

## Purpose
Dar al consultorio el cierre de loop de la lista de espera: cuando una
cancelación libera un hueco, el sistema ofrece al primero compatible con
expiración de 2 h, encadena al siguiente si rechaza/expira, convierte la
aceptación en turno `confirmado` y deja el hueco libre en agenda pública si
nadie acepta — avisando por el canal C-06 con link token — para que el Flujo
6 recupere huecos sin trabajo manual de secretaría (US-012; RN-TU-06,
RN-TU-01/02/03, RN-NO-04, RN-CL-04, RN-GL-02).

## Requirements

### Requirement: Modelo EsperaEntry con estados, vencimiento y token de oferta

El sistema SHALL persistir una fila `EsperaEntry` por espera (`paciente_id
FK, profesional_id nullable FK, especialidad nullable TEXT,
preferencia_horaria JSONB nullable, estado
activa|ofrecida|convertida|vencida, oferta_expira_en nullable TIMESTAMPTZ,
token_oferta_hash nullable, oferta_hueco JSONB nullable, motivo_baja
nullable`) con CHECK (profesional o especialidad presente) y CHECK (toda
`ofrecida` tiene `oferta_expira_en + token_oferta_hash`); la migración SHALL
ser `004_espera.py` sobre `003_notificacion` (renumerando a `005` si C-08 ya
ocupó el `004`, sin cambiar contenido).

#### Scenario: Estado inválido es rechazado por CHECK

- **WHEN** se inserta una espera con `estado='dormida'`
- **THEN** la DB rechaza la fila (CHECK) y nada se encola

#### Scenario: Espera sin destino es rechazada

- **WHEN** se inserta con `profesional_id` y `especialidad` ambos NULL
- **THEN** la DB rechaza la fila (CHECK)

#### Scenario: Migración encadena 003 sin cabezas múltiples

- **WHEN** se corre `alembic heads` tras aplicar la migración del change
- **THEN** hay una sola cabeza y la cadena incluye `003_notificacion`

### Requirement: Matching FIFO al primero compatible

Ante un hueco liberado `{profesional_id, sillon_id, inicio, fin}` el sistema
SHALL elegir la primera entry `activa` en `created_at ASC` tal que
(`profesional_id` NULL o igual), (`especialidad` NULL o contenida en las
especialidades del profesional) y (`preferencia_horaria` NULL/vacía o el
`inicio` cae en sus días/franja); sin compatible SHALL ser no-op con log
(sin ofertas, sin errores).

#### Scenario: Oferta va al primero compatible FIFO

- **WHEN** hay tres activas y la 1ª es incompatible por franja
- **THEN** la 2ª pasa a `ofrecida` con `oferta_expira_en = ahora + 2 h` y la
  1ª y 3ª siguen `activa`

#### Scenario: Sin compatible no pasa nada

- **WHEN** ninguna activa es compatible con el hueco
- **THEN** ninguna entry muta y el hueco queda libre en disponibilidad

### Requirement: Cancelación dispara oferta sin modificar servicios existentes

El sistema SHALL llamar `intentar_ofrecer(hueco)` DESPUÉS de cada
`cambiar_estado→cancelado` en `PATCH /turnos/:id/estado` y en el evento NO
del webhook C-06; `ausente` SHALL NOT disparar oferta; si la oferta falla, el
`cancelado` SHALL conservarse (nunca se revierte por un fallo de espera).

#### Scenario: Cancelar por staff dispara oferta

- **WHEN** secretaría cancela un turno con motivo habiendo una activa
  compatible
- **THEN** el turno queda `cancelado` y la entry queda `ofrecida`

#### Scenario: NO por webhook dispara oferta

- **WHEN** el paciente responde NO y el turno pasa a `cancelado`
- **THEN** la primera compatible queda `ofrecida`

#### Scenario: Ausente no dispara oferta

- **WHEN** un turno pasa a `ausente`
- **THEN** ninguna entry muta

### Requirement: Oferta con expiración 2 h, cascada y hueco libre si nadie acepta

Toda oferta SHALL expirar a las 2 h (`oferta_expira_en`); el rechazo, la
expiración detectada y el barrido del worker (cada 10 min, con lock Redis
`espera:cascada:*`) SHALL marcar `vencida` + ofrecer el mismo hueco al
siguiente compatible en el mismo llamado; si el hueco se tomó entretanto
SHALL marcar `vencida 'hueco_tomado'` y seguir al siguiente; si no quedan
compatibles, el hueco SHALL quedar libre en `GET /disponibilidad` (sin
entries residuales ni turnos basura).

#### Scenario: Rechazo ofrece al siguiente con el mismo hueco

- **WHEN** la entry 1 `ofrecida` es rechazada
- **THEN** queda `vencida` con motivo y la entry 2 queda `ofrecida` con nueva
  ventana de 2 h sobre el mismo hueco

#### Scenario: Expiración 2 h vence y encadena

- **WHEN** pasan 2 h sin respuesta (freezegun +2h01) y corre el barrido
- **THEN** la 1ª queda `vencida 'expirada'` y la 2ª queda `ofrecida`

#### Scenario: Doble disparo no duplica ofertas

- **WHEN** `intentar_ofrecer` corre dos veces seguidas sobre el mismo hueco
- **THEN** existe una sola `ofrecida` para ese hueco (el segundo es skip)

#### Scenario: Nadie acepta y el hueco queda libre

- **WHEN** la cola se vacía o todas vencen sin aceptar
- **THEN** `GET /disponibilidad` pública muestra el hueco ofrecible

### Requirement: Token de oferta un solo uso con aceptar/rechazar públicos

El sistema SHALL emitir token opaco (hash SHA-256 en `token_oferta_hash`,
NULL al consumir) y exponer `POST /lista-espera/aceptar/:token` y `POST
/lista-espera/rechazar/:token` SIN Bearer: hash desconocido SHALL responder
`404` genérico; entry `convertida|vencida` (reuso) SHALL responder `410` sin
mutar; `ofrecida` con `ahora >= oferta_expira_en` SHALL responder `410` +
marcar `vencida` + cascada; el token NUNCA SHALL loguearse.

#### Scenario: Token desconocido es 404

- **WHEN** se acepta con un token jamás emitido
- **THEN** responde `404` y nada muta

#### Scenario: Reuso tras conversión es 410

- **WHEN** se acepta dos veces el mismo token
- **THEN** la primera convierte y la segunda responde `410` sin cambios

#### Scenario: Aceptar expirado es 410 y encadena

- **WHEN** se acepta con ventana vencida habiendo un siguiente compatible
- **THEN** responde `410`, la entry queda `vencida` y el siguiente queda
  `ofrecida`

### Requirement: Conversión crea turno confirmado origen lista_espera

Aceptar (o `POST /:id/convertir` staff) SHALL crear el turno vía
`agenda.crear_turno(origen="lista_espera", sobre_turno=False)` y luego
`agenda.cambiar_estado→confirmado` (dos pasos, contrato C-04 intacto);
la entry SHALL pasar a `convertida` con hash NULL y SHALL encolarse la
plantilla `confirmacion`; si el hueco se tomó entretanto SHALL responder
`409` con alternativas + entry a `vencida 'hueco_tomado'` + cascada
(sobreturno NUNCA SHALL usarse en la conversión).

#### Scenario: Aceptar crea confirmado con origen lista_espera

- **WHEN** se acepta una oferta vigente con hueco libre
- **THEN** existe un turno `confirmado` con `origen=lista_espera` en ese
  hueco y la entry está `convertida`

#### Scenario: Hueco tomado al aceptar es 409 y encadena

- **WHEN** el hueco se ocupó entre la oferta y la aceptación
- **THEN** responde `409` con alternativas, la entry queda `vencida` y el
  siguiente compatible queda `ofrecido`

### Requirement: Aviso de oferta por canal C-06 sin PHI

Al ofrecer, el sistema SHALL crear `Notificacion` plantilla
`oferta_lista_espera` (fila seed `v1`, sin migrar) con variables
`{nombre_pila, fecha, hora, expira_en, link_oferta}` y enviarla por
`whatsapp_cliente` (mock OK); plantilla + payloads SHALL pasar el escáner
sin-PHI; sin número válido SHALL marcar `fallida 'sin_numero_valido'` pero
la entry SHALL seguir `ofrecida` visible en UI (convertible por teléfono y
listada en `GET /notificaciones/pendientes` existente).

#### Scenario: Ofrecer encola notificación de oferta

- **WHEN** se ofrece a una entry con teléfono válido
- **THEN** existe `Notificacion oferta_lista_espera` `encolada/enviada` para
  el turno cancelado que liberó el hueco

#### Scenario: Sin número la oferta sigue en UI secretaría

- **WHEN** el paciente no tiene teléfono válido
- **THEN** la notificación queda `fallida`, la entry sigue `ofrecida` con
  countdown y staff puede convertirla

### Requirement: UI secretaría con cola FIFO, countdown y conversión

El sistema SHALL exponer `CRUD /lista-espera` + `POST /:id/ofrecer` +
`POST /:id/convertir` solo staff (`require_role(secretaria|admin)`) y una
UI `features/lista-espera` con cola ordenada FIFO, estados por color, botón
ofrecer, countdown vivo desde `oferta_expira_en` y botones convertir/baja;
más página pública `/lista-espera/:token` (nombre de pila + fecha/hora +
countdown + Aceptar/Rechazar) que maneja `404/409/410` con mensajes honestos.

#### Scenario: Cola staff ordena FIFO con countdown

- **WHEN** secretaría abre la lista con una `ofrecida` y dos `activa`
- **THEN** ve el orden FIFO, el countdown derivado de `oferta_expira_en` y
  las acciones ofrecer/convertir/baja según estado

#### Scenario: Endpoints staff exigen rol

- **WHEN** se llama `GET /lista-espera` sin Bearer
- **THEN** responde `401`; y con rol no-staff responde `403`
