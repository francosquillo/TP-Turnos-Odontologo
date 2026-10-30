# Design — c-07-lista-espera-cierre-loop

## Context

Ver `proposal.md` (Why). Estado actual: C-04 archivado (tabla `turno` con
doble EXCLUDE parcial, `agenda_servicio` con `crear_turno`/`cambiar_estado`/
`reprogramar`, CHECK `origen IN ('secretaria','online','lista_espera')` —
el origen `lista_espera` ya existe en DB), C-05 archivado (token opaco 256
bits + hash SHA-256 + un solo uso + expiración derivada, con degradación
documentada sin Redis), C-06 archivado (tabla `notificacion` + `plantilla`,
CHECK y `PLANTILLAS` ya incluyen `oferta_lista_espera` con comentario
"reservada para C-07", `whatsapp_cliente` mock/real, `notificacion_servicio`
con barrido idempotente + escáner sin-PHI, `worker/main.py` con
`bucle_notif(3600s)`, `POST /webhooks/whatsapp` con evento NO→`cancelado`,
`GET /notificaciones/pendientes` staff). Head de migraciones verificado
2026-10-14: `backend/alembic/versions/` contiene `001, 002, 003` —
`004` libre (C-08 no lo tomó). Restricciones vinculantes: Pydantic
`extra='forbid'`, `Annotated[..., Depends(...)]` para auth/DB, `async` solo
si todo es async no bloqueante, TS estricto sin `any`, tests contra Postgres
+ Redis reales (nunca SQLite), `freezegun` para la ventana 2 h, TZ
`America/Argentina/Buenos_Aires`, datos 100% ficticios, secretos solo env,
NUNCA PHI por WhatsApp plano, NUNCA `verify` sin Docker en marcha ni permiso
explícito, NUNCA modificar el contrato de `agenda_servicio` (patrón
componer-no-modificar de C-05/C-06).

## Goals / Non-Goals

**Goals:**

- Cola de espera persistente con matching FIFO compatible (Flujo 6, US-012).
- Cancelación (staff o webhook NO) dispara oferta inmediata al primero
  compatible, con expiración 2 h y cascada automática (RN-TU-06).
- Conversión crea turno `confirmado` con `origen=lista_espera` (CA-3) usando
  solo funciones existentes de `agenda_servicio`.
- Aviso por el canal C-06 (oferta con link token; en mock funciona desde el
  día uno; sin número → `fallida` + UI secretaría).
- Si nadie acepta, el hueco queda libre en disponibilidad pública (sin
  residuos: entries `vencida`, sin turnos basura).
- Tasks listas para TDD estricto en apply (RED primero, verificación por task).

**Non-Goals:**

- Modificar `agenda_servicio`, `reserva_servicio`, `notificacion_servicio`,
  `whatsapp_cliente`, máquina de estados, EXCLUDE o endpoints C-04/C-05/C-06
  (solo llamadas aditivas + fila seed).
- Bloquear el hueco durante la oferta (ver D-03: oferta no bloqueante v1.0).
- Ofertas paralelas al mismo paciente, ranking fino de preferencias,
  websocket/push (polling en UI), SMTP/SMS reales (stub C-06 heredado).
- Multi-sede, pagos, AFIP (fuera de v1.0 por reglas duras).

## Decisions

### D-01 — Modelo `EsperaEntry` delgado con estados y token de oferta

Tabla `espera_entry`: `id, paciente_id FK→paciente (RESTRICT), profesional_id
FK→profesional nullable (RESTRICT), especialidad TEXT nullable,
preferencia_horaria JSONB nullable, estado
(activa|ofrecida|convertida|vencida, CHECK), oferta_expira_en TIMESTAMPTZ
nullable, token_oferta_hash TEXT nullable (hash SHA-256, un solo uso, NULL
al consumir — mismo patrón C-05), oferta_hueco JSONB nullable (snapshot
`{profesional_id, sillon_id, inicio, fin}` del hueco ofrecido, para la
cascada y la conversión), motivo_baja TEXT nullable (rechazo/expiración con
traza RN-GL-02), timestamps. Constraints: `CHECK (profesional_id IS NOT NULL
OR especialidad IS NOT NULL)` (toda entry apunta a alguien o a algo),
`CHECK (estado != 'ofrecida' OR (oferta_expira_en IS NOT NULL AND
token_oferta_hash IS NOT NULL))` (toda oferta tiene vencimiento + token).
Índices: `(paciente_id)`, `(estado)` (barrido del worker), `(profesional_id)`
(matching), `created_at` (FIFO). Sin EXCLUDE (no hay solapamiento propio) y
sin UNIQUE global (un paciente puede esperar dos cosas distintas; la
exclusión de doble-oferta es por lógica D-02/D-05, no por DB).
`preferencia_horaria` formato: `{"dias": ["lunes", ...], "desde": "09:00",
"hasta": "13:00"}` (todo opcional; NULL o `{}` = sin preferencia = cualquier
hueco). Esquemas Pydantic estrictos `extra='forbid'`.
Skills: `fastapi`, `postgresql-table-design`, `supabase-postgres-best-practices`.

### D-02 — Punto de enganche: llamada aditiva en la capa API, sin tocar servicios

`lista_espera_servicio.intentar_ofrecer(hueco)` se invoca en DOS puntos,
siempre DESPUÉS de que `cambiar_estado→cancelado` ya commiteó: (a) `PATCH
/turnos/:id/estado` en `api/turnos.py` cuando `nuevo_estado == "cancelado"`;
(b) `api/webhooks.py` evento NO de C-06 cuando cancela. `hueco =
{profesional_id, sillon_id, inicio, fin}` sale del turno recién cancelado.
`agenda_servicio` no se toca (firma intacta); si el servicio de espera falla,
el `cancelado` ya quedó (la cancelación nunca se revierte por un fallo de
oferta: se loguea y el próximo barrido/manual puede re-disparar). El disparo
es sincrónico en-request (latencia: 1 SELECT FIFO + 1 UPDATE + encolado de
aviso; mismo costo que el efecto lateral `confirmacion` de C-05/C-06) y NO un
evento async: la expiración/cascada diferida sí va al worker (D-05).
Alternativas descartadas: modificar `cambiar_estado` para que dispare
(rompe componer-no-modificar y acopla agenda a espera); pub/sub Redis para el
disparo (overkill local, más difícil de testear, sin ganancia de latencia
real); polling del worker sobre cancelados (retrasaría la primera oferta y
exigiría marca "ya ofrecido" redundante con `oferta_hueco`).
Revisión humana en apply: confirmar que el llamado va en los dos puntos (a) y
(b) y en ningún otro (ausente NO dispara: el hueco de un ausente no se
re-oferta en v1.0 — el ausente libera EXCLUDE pero no entra al Flujo 6).
Skills: `fastapi`, `test-driven-development`.

### D-03 — Oferta no bloqueante: el hueco sigue público durante la ventana

Al ofrecer NO se crea ningún turno: el hueco liberado sigue visible en `GET
/disponibilidad` y reservable por vía pública o staff. La oferta es prioridad
de aviso, no reserva. La aceptación compite como cualquier reserva y la DB
(EXCLUDE, C-04) arbitra: si el hueco se tomó entretanto, la conversión falla
con `HuecoOcupadoError` → router responde `409` + la entry pasa a `vencida`
con `motivo_baja='hueco_tomado'` + cascada al siguiente (D-05). Una sola
oferta sobresaliente por entry (`ofrecida` excluye de nuevos matchings hasta
resolverse) y una sola entry `ofrecida` por disparo (cascada secuencial, no
paralela). Alternativa (crear turno `pendiente origen=lista_espera` que
bloquee el hueco 2 h) descartada en v1.0: oculta disponibilidad real durante
la ventana, genera churn de turnos cancelados si expira, y contradice "hueco
libre a agenda pública" como estado natural. Mejora post-TP: reserva blanda
con TTL si la competencia por huecos lo justifica.
Skills: `redis-patterns` (lock de cascada D-05), `fastapi`.

### D-04 — Token de oferta: réplica del patrón C-05, sin Redis

`generar_token()` opaco 256 bits + `hash_token()` SHA-256 (se importan de
`reserva_servicio`, no se duplican); en DB solo el hash
(`token_oferta_hash`), un solo uso (NULL al aceptar/rechazar). Expiración
DERIVADA de `oferta_expira_en` (columna propia, no `min(72h, inicio)` como
C-05: la ventana es 2 h desde la oferta, independiente del inicio del turno).
Diferencia con C-05: NO necesita set Redis de usados — la máquina de la
entry ya distingue reuso (`convertida|vencida` → `410`) de desconocido (hash
inexistente → `404` genérico) y de expirado (`ofrecida` con `ahora >=
oferta_expira_en` → `410` + cascada). `POST /lista-espera/aceptar/:token` y
`POST /lista-espera/rechazar/:token` son públicos SIN Bearer (el hash ES la
auth, igual que `GET /confirmar/:token`); esquemas `extra='forbid'`; el token
nunca se loguea. El link enviado es `{FRONTEND_URL}/lista-espera/:token`
(página pública mínima con countdown + botones Aceptar/Rechazar, paralela a
`pages/confirmar` de C-05).
Skills: `fastapi`, `python-testing-patterns`.

### D-05 — Expiración 2 h y cascada: DB autoritativa + worker cada 10 min + lock Redis

`oferta_expira_en = ahora + 2 h` al ofrecer (constante
`OFERTA_EXPIRA_HORAS = 2`, testeada con `freezegun`). Tres vías llevan a
`vencida` + cascada `intentar_ofrecer(mismo oferta_hueco)`: (1) rechazo
explícito (token o staff) → cascada inmediata en-request; (2) expiración
detectada al intentar aceptar (`410` + cascada inmediata); (3) barrido del
worker `espera_jobs.barido_vencidas()` cada 10 min (`bucle_espera(600s)` en
`worker/main.py`, junto a `bucle_notif`, sin servicio compose nuevo) para
ofertas que nadie tocó. Anti-doble-cascada: lock Redis
`espera:cascada:{profesional_id}:{sillon_id}:{inicio_iso}` con `SET NX EX
900s` (mismo helper `_reservar_clave` de C-06); con Redis caído se degrada a
barrido DB idempotente (re-marcar `vencida` es no-op; `intentar_ofrecer`
excluye `ofrecidas`, así que el peor caso es una oferta duplicada al
siguiente, aceptable y testeado). Regla de cascada: `intentar_ofrecer`
excluye entries `ofrecida` y, ante hueco ya tomado (EXCLUDE/ocupados),
marca la entry `vencida 'hueco_tomado'` y SIGUE al siguiente en el mismo
llamado (cascada intra-llamado, sin esperar al worker).
Skills: `redis-patterns` (SET NX EX, TTL 15 min), `fastapi`,
`test-driven-development`.

### D-06 — Conversión en dos pasos con funciones existentes (CA-3)

Aceptar (token válido + `ofrecida` + vigente) SHALL: (1)
`agenda.crear_turno(..., origen="lista_espera", sobre_turno=False)` — nace
`pendiente` porque `crear_turno` solo mapea `secretaria→confirmado`
(NO se cambia ese mapeo: es contrato C-04); (2)
`agenda.cambiar_estado(turno, "confirmado")` — transición permitida
`pendiente→confirmado`; (3) entry → `convertida` + `token_oferta_hash=NULL`;
(4) encola plantilla `confirmacion` como efecto lateral (igual que C-06
5.2/6.1). Si (1) levanta `HuecoOcupadoError` → entry a `vencida
'hueco_tomado'` + cascada + `409` con alternativas (re-oferta simétrica a
C-04/C-05). `POST /lista-espera/:id/convertir` (staff, paciente que aceptó
por teléfono) ejecuta el mismo núcleo con `paciente_id/profesional/sillon/
inicio/fin` del `oferta_hueco`. UNIQUE/modalidad sobreturno NO aplican (la
oferta convierte a turno normal confirmado, nunca `sobre_turno=true`).
Revisión humana en apply: confirmar los dos pasos (vs. mapear
`lista_espera→confirmado` dentro de `crear_turno`, que se descarta por
romper contrato C-04).
Skills: `fastapi`, `python-testing-patterns`.

### D-07 — Aviso con `oferta_lista_espera` seed `v1`, sin migrar, sin PHI

C-06 dejó el CHECK y `PLANTILLAS` con `oferta_lista_espera` incluida + el
test `test_plantilla_hueco_extensible_a_oferta`: este change SOLO añade la
fila seed `v1` en `seed_plantillas.py` (upsert `nombre+version`, idempotente)
con cuerpo `"Hola {nombre_pila}, se liberó un turno el {fecha} a las {hora}.
Tenés 2 h para confirmarlo aquí: {link_oferta} (vence {expira_en})."` y
variables declaradas `{nombre_pila, fecha, hora, expira_en, link_oferta}`.
El envío usa `notificacion_servicio` + `whatsapp_cliente` (mock OK; real con
costo `0.026` heredado); `turno_id` de la fila: el turno cancelado que liberó
el hueco (trazabilidad; el UNIQUE parcial no colisiona porque la plantilla es
nueva por turno). Escáner sin-PHI de C-06 cubre la plantilla + payloads (solo
nombre de pila + fecha/hora + link; NUNCA diagnóstico/pieza/OS/monto). Sin
número válido → fila `fallida 'sin_numero_valido'` (D-06 de C-06) + la entry
SIGUE `ofrecida` visible en UI secretaría con countdown (puede convertir por
teléfono vía `POST /:id/convertir`); además aparece en `GET
/notificaciones/pendientes` existente (sin endpoint nuevo de avisos).
Skills: `fastapi`, `python-testing-patterns`.

### D-08 — Migración `004_espera` (head verificado, sin colisión)

Verificado 2026-10-14: `backend/alembic/versions/` = `001_core_identidad_
pacientes, 002_turno, 003_notificacion` (una sola cabeza). Este change propone
`004_espera.py` (tabla + CHECKs D-01 + índices; `down_revision =
'003_notificacion'`). El apply SHALL re-verificar el head al inicio y, si
C-08 generó `004_*` entretanto, renumerar a `005_espera.py` (solo nombre +
`down_revision`; contenido intacto, tablas disjuntas). Rollback: `alembic
downgrade -1` (sin datos reales en v1.0). Test RED
`test_c07_migracion_head_encadena_003` (una sola cabeza, cadena incluye
`003_notificacion`).

## Risks / Trade-offs

- [Oferta no bloqueante: el paciente acepta y el hueco ya se tomó → 409
  frustrante] → Mitigación: D-03/D-06 convierten el 409 en cascada + re-oferta
  con alternativas (misma UX que el 409 de C-04/C-05); el link muestra el
  countdown y "sujeto a disponibilidad".
- [Cascada lenta: N entries × 2 h pueden tardar días en recorrer la cola] →
  Aceptado v1.0 (RN-TU-06 fija 2 h por oferta); mitigación: `POST /:id/ofrecer`
  manual permite a secretaría saltear/adelantar, y el orden FIFO es auditable.
- [Doble tick del worker o rechazo+barrido concurrentes ofrecen dos veces] →
  Mitigación: lock Redis `espera:cascada:*` + exclusión de `ofrecidas` en el
  matching (D-05); test de doble barrido exige una sola `ofrecida` por hueco.
- [Hook en dos puntos API: un tercer camino a `cancelado` futuro no dispara] →
  Mitigación: documentar en el servicio que todo nuevo camino a `cancelado`
  SHALL llamar `intentar_ofrecer`; test de integración cubre router + webhook.
- [`ausente` libera EXCLUDE pero no dispara oferta (decisión D-02)] → Riesgo
  aceptado y documentado; si la facultad lo pide, es un cambio de una línea
  (añadir el tercer punto) con test.
- [Token en link WhatsApp/SMS: quien tenga el link acepta el turno] →
  Mismo riesgo aceptado que C-05 (token opaco, un solo uso, expira 2 h,
  sin PHI en el mensaje); mitigación adicional: la página de aceptar muestra
  solo nombre de pila + fecha/hora.
- [Matching por especialidad `contains` puede ofrecer fuera de preferencia
  fina] → Mitigación: `preferencia_horaria` filtra día/franja; lo no
  expresado se asume flexible; secretaría puede dar de baja entries
  obsoletas (CRUD incluye baja con motivo).
- [Frontend countdown por polling desincroniza segundos] → Aceptado v1.0
  (la expiración autoritativa es DB + `freezegun` en tests); el countdown es
  informativo y se recalcula contra `oferta_expira_en` del GET.

## Migration Plan

1. Mergear solo artefactos openspec (este change: sin código).
2. Apply (TDD, orden): modelo + migración 004 (verificar head 003, D-08) →
   repo + matching FIFO → `lista_espera_servicio` (ofrecer/expirar/cascada/
   tokens) → endpoints staff + públicos + hooks en `turnos.py`/`webhooks.py`
   (aditivos) → seed `oferta_lista_espera v1` + envío vía C-06 → conversión
   dos pasos (D-06) → `espera_jobs` + `bucle_espera` en worker → frontend
   `features/lista-espera` + página aceptar → suite verde (`pytest
   backend/app/tests` contra PG + Redis reales, nunca SQLite; `freezegun`
   para 2 h).
3. Rollback: revertir código + `alembic downgrade -1` (borra tabla + entries;
   notificaciones `oferta_lista_espera` quedan como traza, igual que C-06);
   claves `espera:*` expiran solas (TTL 15 min) o `redis-cli DEL`.
4. `openspec validate --change c-07-lista-espera-cierre-loop --strict` antes
   de archivar; archivar marca `[x]` C-07 en `CHANGES.md` (GATE 6 sigue con
   C-09/C-10/C-11 en paralelo; C-07 no bloquea a nadie).

## Open Questions

- (D-02 — revisión humana en apply, no bloquea specs/tasks): ¿`ausente`
  dispara oferta como `cancelado`, o se mantiene fuera del Flujo 6 en v1.0?
  (propuesta: fuera — documentado).
- (D-06 — revisión humana en apply): ¿conversión en dos pasos
  (`crear_turno` + `cambiar_estado`) o mapear `lista_espera→confirmado`
  dentro de `crear_turno`? (propuesta: dos pasos, contrato C-04 intacto).

## UI Mockups

- Design system revision: 1 (design-system/README.md, aprobado 2026-10-28)
- Decision: no (project policy) — modo system-only, 2026-10-28

## Resoluciones humanas (2026-10-28)

Desvíos surgidos en el apply, aceptados por el usuario:

1. **Sin pre-chequeo de solapamiento al ofrecer (ajusta D-03).** `intentar_ofrecer` ya no verifica si el hueco está ocupado: con el hueco ocupado quemaba toda la cola. El hueco se arbitra al aceptar (EXCLUDE/ocupados → 409 + entry `vencida 'hueco_tomado'` + cascada al siguiente). Puede re-ofrecerse un hueco ya tomado; es aceptable.
2. **Hash del token como tombstone (ajusta D-04).** Tras consumir la oferta, `token_oferta_hash` se conserva en la fila para que un reuso (aceptar o rechazar) responda 410 en vez de 404.
3. **Notificación previa a `fallida` en cascada (ajusta D-07).** Al pasar la oferta al siguiente, la notificación anterior del mismo turno se marca `fallida` con motivo `oferta_superada`, para no violar el UNIQUE `(turno_id, plantilla)` de C-06.

4. **Criterio de `openspec validate` para archivar (2026-10-30).** El usuario definió que 0 errores cuenta como verde. Los warnings "requirement >500 caracteres" (1 de C-07 y 7 en specs anteriores) se aceptan y no se reescriben.
