# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Stack impuesto por la facultad
**Decisión**: Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis + Docker/Compose; React + TS + Vite.
**Contexto**: la facultad fijó el stack; discovery §9 lo dejaba abierto y ahora quedó cerrado.
**Alternativas consideradas**: ninguna (no negociable).
**Justificación**: homogeneidad evaluable entre grupos; cubre todo el MVP.
**Trade-offs aceptados**: sin SSR (Vite SPA), sin ORM multi-DB.

### DD-02 — Monolito modular, no microservicios
**Decisión**: un backend FastAPI por capas + worker Redis en el mismo compose.
**Contexto**: equipo de 3, TP evaluable, deploy simple.
**Alternativas**: microservicios por dominio; serverless.
**Justificación**: el dominio cabe en un esquema; microservicios multiplican infra sin beneficio.
**Trade-offs**: escalamiento vertical primero; extraer servicios solo post-TP si hace falta.

### DD-03 — Anti-solapamiento a nivel base de datos
**Decisión**: constraint `EXCLUDE` por profesional y por sillón.
**Contexto**: discovery exige "choque imposible" (Órbita/DentalSoft AR lo tienen).
**Alternativas**: solo validación en aplicación.
**Justificación**: la app tiene carreras concurrentes (reserva online + secretaría); solo la DB garantiza.
**Trade-offs**: requiere extensión `btree_gist`; tests con Postgres real (no SQLite).

### DD-04 — Redis para todo lo async
**Decisión**: recordatorios, webhooks salientes, exports CSV/PDF vía cola Redis.
**Contexto**: el stack incluye Redis; WhatsApp cobra por mensaje y falla.
**Justificación**: reintentos + idempotencia sin bloquear requests.
**Trade-offs**: un componente más en compose; jobs idempotentes obligatorios.

### DD-05 — Paciente sin cuenta en v1.0
**Decisión**: reserva pública + token un solo uso; sin portal ni password de paciente.
**Contexto**: el portal es etapa posterior (discovery §6); el TP premia reserva + confirmación.
**Justificación**: menos superficie de auth, menos fricción de adopción.
**Trade-offs**: el historial online del paciente espera al portal post-TP.

### DD-06 — MVP doble pista
**Decisión**: núcleo académico evaluable + 6 diferenciadores acotados (lista de espera, validador OS, reseñas, exportación total, página seguridad, costo WhatsApp visible).
**Contexto**: TP que puede escalar a producto (discovery Anexo D).
**Justificación**: el núcleo aprueba; los diferenciadores separan del promedio sin explotar alcance.
**Trade-offs**: IA, pagos y fiscal quedan explícitamente fuera.

## Supuestos inferidos (actualizados 2026-10-05 con decisiones del equipo)

### SU-01 — Sin consultorio piloto real [RESUELTO 2026-10-05]
**Decisión**: NO hay piloto real. Datos 100% ficticios y de prueba obligatorio para el TP.
**Origen**: pregunta abierta respondida por el equipo.
**Implicancia**: modelo, arquitectura y roadmap quedan preparados para futura producción real (RN-GL-03 aplica al escalar).
**Supuesto WhatsApp que se mantiene** (discovery §10): los pacientes confirman por WhatsApp en vez de ignorar; si es falso cae el mecanismo anti-ausentismo. Fallback email/SMS ya previsto.

### SU-02 — Las OS aceptan liquidación CSV/PDF por nomenclador
**Supuesto**: el formato exportado sirve para presentar reintegros.
**Origen**: discovery §10 (cada prestadora exige su formato).
**Riesgo si es falso**: la liquidación digital no cierra el circuito.
**Decisión 2026-10-05 [RESUELTO parcial]**: nomenclador de prueba con OS ficticia ("OS Ficticia Demo"); formato real de cada prestadora queda para escalamiento.

### SU-03 — Sede única en v1.0 [RESUELTO 2026-10-05]
**Decisión**: sede única alcanza en v1.0; sin multi-sede. El modelo `Sillon.sede` como texto queda extensible post-TP.
**Origen**: inferido — ningún caso de uso exige multi-sede.

### SU-04 — Nomenclador de prueba disponible [RESUELTO 2026-10-05]
**Decisión**: OS ficticia ("OS Ficticia Demo" + planes/aranceles de ejemplo) para seed y demo.
**Origen**: discovery §11 (pregunta abierta respondida por el equipo).
