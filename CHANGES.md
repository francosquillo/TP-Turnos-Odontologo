# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto TP-Turnos-Odontologo.
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

> **Restricciones del checkpoint 2026-10-05 (vinculantes para todos los changes):**
> Prioridad 1 = Turnos/Agenda (Épica A+B primero) · Plazo duro 12/10/2026 (~7 días, equipo 3)
> Sede única v1.0 (`Sillon.sede` texto extensible) · Rol simple FK (`usuario.rol_id`, sin tabla intermedia)
> Dueño = Admin (alias, sin rol separado) · Pagos simulados (sin MP real) · AFIP post-TP
> OS ficticia ("OS Ficticia Demo") · Deploy local Docker Compose · Datos 100% ficticios, arquitectura prod-ready.

---

## Cómo usar este documento

1. Identificá el próximo change pendiente (`- **Estado**: [ ]`) respetando dependencias y GATES.
2. Leé los archivos de **Leer antes** de ese change en `knowledge-base/` (son la fuente de verdad).
3. Ejecutá `/opsx:propose C-NN-nombre` para crear la propuesta de ese change.
4. Implementá con `/opsx:apply`, luego archivá con `/opsx:archive`.
5. Marcá el checkbox `- **Estado**: [x]` acá cuando el change esté archivado.

---

## Árbol de dependencias

```
C-01 foundation-setup
└── C-02 core-models-identidad-pacientes
    └── C-03 auth-rbac
        ├── C-04 agenda-turnos-core ⭐
        │   ├── C-05 reserva-online-publica
        │   │   └── C-12 admin-cierre-demo (parcial: necesita C-05 para front reservas)
        │   ├── C-06 notificaciones-whatsapp
        │   │   └── C-07 lista-espera-cierre-loop
        │   └── C-09 presupuestos-cuenta-corriente (también ← C-08)
        │       ├── C-10 caja-cobros-simulados
        │       └── C-11 obras-sociales-liquidacion
        ├── C-08 clinica-odontograma-hc
        │   └── C-09 presupuestos-cuenta-corriente
        └── C-12 admin-cierre-demo (base: C-02 + C-03)
```

### Paralelismo por fase

```
GATE 0: C-01 ✓
  → C-02 core-models-identidad-pacientes   [Agente A]

GATE 1: C-02 ✓
  → C-03 auth-rbac                          [Agente A]

GATE 2: C-03 ✓                              ← PRIMER FORK
  → C-04 agenda-turnos-core                 [Agente A — Backend Core, PRIORITARIO]
  → C-08 clinica-odontograma-hc             [Agente B — Backend Aux]
  → C-12 admin-cierre-demo (base usuarios/import/seguridad) [Agente C — Frontend/Admin]

GATE 3: C-04 ✓                               ← FORK turnos
  → C-05 reserva-online-publica             [Agente A]
  → C-06 notificaciones-whatsapp (modo mock si no hay creds Meta) [Agente C — si C-05 en curso, contrato token ya definido]
  → C-08 continúa en paralelo si no terminó [Agente B]

GATE 4: C-04 ✓ + C-08 ✓
  → C-09 presupuestos-cuenta-corriente      [Agente B]
  → C-06 termina / C-05 termina             [Agente A/C]

GATE 5: C-04 ✓ + C-06 ✓
  → C-07 lista-espera-cierre-loop           [Agente A o C]

GATE 6: C-09 ✓                               ← FORK cobros
  → C-10 caja-cobros-simulados              [Agente B]
  → C-11 obras-sociales-liquidacion         [Agente C — si C-04 ✓]
  → C-07 termina en paralelo                [Agente A]
```

### Camino crítico (7 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-04 → C-05 → C-09 → C-10
```

Cadena E2E evaluable: infra → identidad → auth → agenda → reserva pública → presupuesto/CC → caja simulada.
Variante turnos-pura (misma longitud): `C-01 → C-02 → C-03 → C-04 → C-05 → C-06 → C-07`.
No incluye: reseñas Google, página seguridad extendida, exportación total (viven en C-12, paralelizable).

### Plan óptimo con 3 agentes

| Paso | Agente A (Backend Core — turnos) | Agente B (Backend Aux — clínica/cobros) | Agente C (Frontend/Admin + notif) |
|---|---|---|---|
| 1 (día 1 AM) | C-01 foundation-setup | — (apoya C-01: seed/compose) | — (apoya C-01: scaffold Vite) |
| 2 (día 1 PM) | C-02 modelos identidad | — (review C-02) | — (prepara shell SPA + auth-context) |
| 3 (día 2 AM) | C-03 auth-rbac | C-08 clínica (arranca con contratos C-02) | C-12 base (usuarios UI, import Excel, página seguridad) |
| 4 (día 2 PM–3) | C-04 agenda-turnos ⭐ | C-08 termina | C-12 base termina |
| 5 (día 4) | C-05 reserva online | C-09 presupuestos/CC (si C-08 ✓) | C-06 notif mock |
| 6 (día 5) | C-07 lista de espera | C-10 caja simulada (si C-09 ✓) | C-11 OS/liquidación (si C-04 ✓ + C-09 ✓) |
| 7 (día 6) | E2E turnos + fixes | E2E clínica/caja + fixes | E2E OS/admin + demo seed |
| 8 (día 7, colchón) | Demo + defensa | Demo + defensa | Demo + defensa |

Estimación vs plazo 12/10: 12 changes × ~5 h = ~60 h totales / 3 personas = ~20 h por persona en 7 días (~3 h/día). Factible con paralelismo agresivo; si hay retraso, recortar en este orden: C-07 → C-11 (export PDF) → C-12 (reseñas), nunca C-04/C-05.

---

## FASE 1 — Fundación e identidad

> Cuello de botella corto y secuencial (C-01 → C-02 → C-03). No paralelizar: todo depende de esto.

### [C-01] `foundation-setup`
- **Estado**: `[x]` archivado 16/16 (2026-10-06) → `openspec/changes/archive/2026-10-06-c-01-foundation-setup/` — verificado E2E Docker por el usuario: suite verde (`docker compose up -d --build` + suite completa, incluye 2 tests de config + btree_gist contra PG real)
- **Scope**:
  - `docker-compose.yml`: servicios `api + worker + postgres:16 + redis:7` (solo local, sin cloud)
  - `backend/Dockerfile + app/main.py`: FastAPI, routers vacíos, middlewares CORS, healthcheck `/health`
  - `backend/app/core/`: config por env (`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_EXPIRE_MIN, WHATSAPP_*, GCAL_*, CORS_ORIGINS, SEED_ADMIN_*, TZ=America/Argentina/Buenos_Aires`), `.env.example` (`.env` no versionado)
  - Estructura capas `api/ servicios/ repos/ modelos/ esquemas/ worker/ tests/` según `08`
  - `frontend/`: Vite + React 18 + TS 5, `src/shared/api-client, auth-context`, `src/pages/` vacías, `Dockerfile`
  - Extensión Postgres `btree_gist` habilitada en init SQL (requisito DD-03)
  - Tests: healthcheck, import smoke, compose up verificado
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md`
  - `knowledge-base/02_descripcion_general.md`
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-01, §DD-02

### [C-02] `core-models-identidad-pacientes`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `Rol, Usuario (rol_id FK, un rol por usuario), Paciente, Profesional, Sillon (sede texto, sede única)`
  - Migración 001: tablas + índices (`usuario.email unique, paciente.dni, apellido, telefono`), constraint `>=1 admin activo` (a nivel servicio, no DB)
  - Repos genéricos + base repository sobre SQLAlchemy 2 async
  - Seed: roles fijos `admin/odontologo/secretaria` (+ alias Dueño=Admin, sin tabla extra), 1 admin inicial, 1 sillón demo, 1 profesional demo con `agenda_config` JSON semanal
  - Soft-delete en Paciente (`deleted_at`, RN-GL-01)
  - Tests: CRUD pacientes, unique email/dni, FK rol simple (rechaza segundo rol), seed idempotente
- **Dependencias**: `C-01`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Usuario, §Paciente, §Profesional, §Sillon
  - `knowledge-base/03_actores_y_roles.md`
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AU-03, §RN-GL-01
  - `knowledge-base/10_preguntas_abiertas.md` §IN-01, §IN-02

### [C-03] `auth-rbac`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `POST /auth/login` (email+password, 401 genérico sin enumerar), `POST /auth/refresh` (rotativo httpOnly), `GET /auth/me`, `POST /auth/logout`
  - JWT Bearer corto (`JWT_EXPIRE_MIN=30`) + hash Argon2/bcrypt
  - Dependencia FastAPI `require_role(...)` con matriz `03` (admin/odontologo/secretaria + público)
  - Resguardo último admin: bloquea desactivar/eliminar si es el único activo (RN-AU-03)
  - Frontend: `auth-context`, login page, guard de rutas por rol
  - Tests: login/refresh/logout, RBAC por endpoint, bloqueo último admin, token expirado → 401
- **Dependencias**: `C-02`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md`
  - `knowledge-base/07_flujos_principales.md` §Flujo 7
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AU-01, §RN-AU-02, §RN-AU-03
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad

---

## FASE 2 — Turnos y agenda ⭐ PRIORITARIA

> Lo que más pondera la evaluación. Agente A a tiempo completo acá hasta C-05 verde.

### [C-04] `agenda-turnos-core`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `Turno (paciente_id, profesional_id, sillon_id, inicio, fin, estado, origen, token_confirmacion hash nullable, sobre_turno bool)`
  - Migración 002: tabla turno + constraints `EXCLUDE USING gist (profesional WITH =, tstzrange WITH &&)` ídem sillón; sobreturno solo con `sobre_turno=true + motivo` auditado (RN-TU-02, RN-GL-02)
  - Endpoints: `CRUD /turnos`, `PATCH /turnos/:id/estado`, `GET /disponibilidad?profesional&desde&hasta` (respeta horario profesional + RN-TU-01), `GET /agenda?vista=dia|semana|mes&profesional&sillon`
  - Servicio agenda: cálculo huecos = horario semanal − turnos existentes; reprogramar revalida solapamiento; cancelar exige motivo
  - Frontend `features/agenda`: vistas día/semana/mes, colores por estado, drag para reprogramar (409 → re-oferta)
  - Tests (Postgres real, no SQLite): anti-solapamiento concurrente, sobreturno auditado, estados, disponibilidad
- **Dependencias**: `C-02, C-03`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Turno
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-01, §RN-TU-02, §RN-TU-03, §RN-TU-05
  - `knowledge-base/06_funcionalidades.md` §US-001, §US-003
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-03

### [C-05] `reserva-online-publica`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Rutas públicas: `POST /reservas` (crea turno `pendiente` + token un solo uso, expira 72 h o al inicio; crea/matchea paciente mínimo nombre+teléfono), `GET /disponibilidad` pública, `GET /confirmar/:token` (confirma → `confirmado`; expirado → pantalla con teléfono consultorio)
  - Token: hash en DB, un solo uso, expiración (RN-TU-04); confirmación actualiza agenda sin intervención (RN-TU-03)
  - Frontend `pages/reservas, pages/confirmar`: selector profesional/día/hora, formulario mínimo, pantalla éxito/error; `GET /` landing; manejo 409 hueco tomado → re-oferta
  - Tests: reserva crea pendiente+token, confirmar actualiza, reuso token → 410, expirado → alternativa contacto, concurrente → 409
- **Dependencias**: `C-04`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §Rutas públicas
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-03, §RN-TU-04, §RN-TU-05
  - `knowledge-base/06_funcionalidades.md` §US-002, §US-011
  - `knowledge-base/07_flujos_principales.md` §Flujo 1

### [C-06] `notificaciones-whatsapp`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `Notificacion (canal, plantilla, turno_id, estado, costo, payload sin PHI)`, plantillas seed: recordatorio 48/24 h, confirmación, hueco liberado, reseña Google
  - Worker Redis + cron horario: busca turnos `pendiente|confirmado` a 48/24 h, encola idempotente (`turno_id+tipo`), reintentos; registra estado + costo Meta (USD 0,026/ref visible)
  - `POST /webhooks/whatsapp` (verifica firma Meta, RN-AU-04; sin firma → 401+log); respuesta paciente actualiza turno; sin número válido → `fallida` + avisa secretaría
  - Modo mock por env (`WHATSAPP_MOCK=true`) para demo sin creds Meta; fallback email/SMS stub si WhatsApp falla (RN-NO-03)
  - Prohibido PHI en cuerpo (RN-CL-04/RN-NO-04)
  - Tests: idempotencia encolado, firma webhook, actualización turno vía webhook, fallback, sin PHI en payload
- **Dependencias**: `C-04`
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Notificacion
  - `knowledge-base/05_reglas_de_negocio.md` §RN-NO-01..04, §RN-AU-04, §RN-CL-04
  - `knowledge-base/06_funcionalidades.md` §US-010, §US-011
  - `knowledge-base/07_flujos_principales.md` §Flujo 2
  - `knowledge-base/08_arquitectura_propuesta.md` §Worker + cola

### [C-07] `lista-espera-cierre-loop`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelo `EsperaEntry (paciente_id, profesional_id/especialidad, preferencia_horaria, estado activa|ofrecida|convertida|vencida)`
  - Endpoints: `CRUD /lista-espera`, `POST /lista-espera/:id/ofrecer`, conversión a turno `confirmado`
  - Servicio: al cancelarse turno, ofrece al primero compatible con expiración **2 h** (RN-TU-06); rechaza/expira → cascada al siguiente; nadie acepta → hueco libre a agenda pública
  - Reutiliza C-06 para aviso (oferta con link token); si C-06 en mock, aviso simulado en UI secretaría
  - Frontend `features/lista-espera`: cola ordenada, botón ofrecer, countdown 2 h, conversión
  - Tests: oferta al primero, expiración 2 h, cascada, conversión crea confirmado, hueco liberado si nadie acepta
- **Dependencias**: `C-04, C-06`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §EsperaEntry
  - `knowledge-base/05_reglas_de_negocio.md` §RN-TU-06
  - `knowledge-base/06_funcionalidades.md` §US-012
  - `knowledge-base/07_flujos_principales.md` §Flujo 6

---

## FASE 3 — Clínica, cobros y OS

> C-08 corre en paralelo a C-04 desde GATE 2. C-09 es el join (necesita clínica + turnos).

### [C-08] `clinica-odontograma-hc`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `HistoriaClinica (paciente_id unique, antecedentes, alergias)`, `HallazgoOdontograma (hc_id, pieza_fdi 11–48, cara, estado catálogo cerrado versionado, profesional_id)`, `Tratamiento` catálogo (código interno + código_nomenclador nullable, nombre, precio_base)
  - Migración 003: HC + hallazgos + catálogo; índice `(hc_id, pieza_fdi)`; soft-delete HC
  - Endpoints: `CRUD /historias`, `CRUD /odontograma/:hc_id/hallazgos`, `GET /tratamientos`, alergias siempre visibles en respuesta
  - Frontend `features/odontograma`: grilla FDI 11–48, caras, historial por pieza, sin PHI en logs
  - Tests: FDI válido/inválido, catálogo cerrado, historial por pieza, soft-delete
- **Dependencias**: `C-02, C-03`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §HistoriaClinica, §Tratamiento
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CL-03, §RN-CL-04, §RN-GL-01
  - `knowledge-base/06_funcionalidades.md` §US-020, §US-021
  - `knowledge-base/07_flujos_principales.md` §Flujo 3

### [C-09] `presupuestos-cuenta-corriente`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `Presupuesto (paciente_id, profesional_id, estado borrador|presentado|aceptado|rechazado|cobrado, total)`, `ItemPresupuesto (presupuesto_id, tratamiento_id/hallazgo_id, cantidad, precio)`; `CuentaCorriente (paciente_id unique, saldo derivado)`, `Movimiento (cc_id, tipo cargo|pago|ajuste, monto != 0, turno_id/presupuesto_id/recibo_id nullable)`
  - Regla: presupuesto nace de hallazgos (cada ítem referencia hallazgo, RN-CL-01); estados hasta aceptado/cobrado o rechazado con motivo (RN-CL-02); aceptado → cargo automático a CC; saldo derivado nunca editable (RN-CO-03); anulación vía contramovimiento
  - Endpoints: `CRUD /presupuestos`, `POST /presupuestos/:id/aceptar|rechazar`, `GET /cuentas/:paciente_id` (deuda, cargos, pagos)
  - Frontend `features/presupuestos, features/cuenta-corriente`: crear desde odontograma, ver deuda
  - Tests: ítem sin hallazgo → 422, flujo estados, cargo a CC, saldo derivado, contramovimiento
- **Dependencias**: `C-08, C-04`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Tratamiento/Presupuesto, §CuentaCorriente
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CL-01, §RN-CL-02, §RN-CO-02, §RN-CO-03
  - `knowledge-base/06_funcionalidades.md` §US-022, §US-030
  - `knowledge-base/07_flujos_principales.md` §Flujo 3

### [C-10] `caja-cobros-simulados`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `Caja (fecha unique, abierta_por, estado abierta|cerrada, total_sistema, total_contado, diferencia)`, `MovimientoCaja (caja_id, medio efectivo|transferencia|tarjeta_simulada, monto, recibo_id)`, `Recibo (número secuencia sin huecos, paciente_id, monto, medio, anulado+motivo)`
  - Medios **simulados** (sin integración MP real); cierre diario obligatorio bloquea operar día siguiente (RN-CO-01); diferencia ≠ 0 exige declararla; anular → contramovimiento + motivo (RN-CO-02); recibo secuencial sin huecos (RN-CO-04)
  - Endpoints: `POST /caja/cobrar` (CC → recibo + movimiento CC + movimiento caja), `POST /caja/cierre`, `POST /recibos/:id/anular`
  - Frontend `features/caja`: cobrar, cierre con diferencia, bloqueo día siguiente
  - Tests: secuencia recibos sin huecos, cierre obligatorio, diferencia declarada, anulación trazada
- **Dependencias**: `C-09`
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §Caja/CierreDiario/Recibo
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CO-01..04
  - `knowledge-base/06_funcionalidades.md` §US-031
  - `knowledge-base/07_flujos_principales.md` §Flujo 4

### [C-11] `obras-sociales-liquidacion`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - Modelos: `ObraSocial, Plan, Arancel (código_nomenclador, precio, vigencia_desde/hasta)`, `Liquidacion (os_id, período mes, estado borrador|presentada|cobrada, total)`, `ItemLiquidacion (prestación turno_id/tratamiento, arancel aplicado, monto)`
  - Seed OS ficticia "OS Ficticia Demo" + planes/aranceles ejemplo; arancel vigente a fecha prestación (RN-OS-03); prestación sin arancel → fila revisión manual
  - Endpoints: `CRUD /obras-sociales /planes /aranceles`, `POST /liquidaciones` (por OS+período), `GET /liquidaciones/:id/export.csv|pdf`, `GET /validador-cobertura?paciente&tratamiento` (muestra cubierto vs a cargo, RN-OS-01)
  - Export CSV + PDF presentable (vía worker Redis si pesado)
  - Tests: vigencia arancel, agrupado OS/plan/período, export CSV/PDF, validador
- **Dependencias**: `C-04, C-09`
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §ObraSocial/Plan/Arancel/Liquidacion
  - `knowledge-base/05_reglas_de_negocio.md` §RN-OS-01..03
  - `knowledge-base/06_funcionalidades.md` §US-040, §US-041
  - `knowledge-base/07_flujos_principales.md` §Flujo 5

---

## FASE 4 — Admin y cierre demo

> Paralelizable desde GATE 2 (base) y completada al final (E2E + seed demo). Si el plazo aprieta, recortar reseñas primero.

### [C-12] `admin-cierre-demo`
- **Estado**: `[ ]` pendiente
- **Scope**:
  - `CRUD /admin/usuarios` (matriz `03`, resguardo último admin ya en C-03, UI gestión); `CRUD /admin/aranceles` (versión simple, audita cambios RN-GL-02)
  - `POST /pacientes/import` Excel/CSV con reporte errores por fila + `GET /admin/export-total` (descargable anti-lock-in, vía worker)
  - `GET /seguridad` página pública (cifrado, respaldos, auditoría — contenido honesto verificable, datos ficticios declarados)
  - Reseña Google post-turno: link/redirect automático (no API escritura)
  - Google Calendar sync por profesional: stub con flag (sincronización real solo si hay creds; si no, deshabilitado con mensaje)
  - Seed demo completo + compose local verificado E2E (landing → reserva → confirmar → agenda → odontograma → presupuesto → cobrar → cierre → liquidación)
  - Tests: import con filas malas, export total, página seguridad pública, resguardo admin vía UI
- **Dependencias**: `C-02, C-03` (base); E2E final requiere `C-05, C-10` verdes
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §RBAC, §Rutas públicas
  - `knowledge-base/06_funcionalidades.md` §US-050, §US-051, §US-052
  - `knowledge-base/05_reglas_de_negocio.md` §RN-GL-01, §RN-GL-02
  - `knowledge-base/08_arquitectura_propuesta.md` §Despliegue, §Variables de entorno
  - `knowledge-base/02_descripcion_general.md` §Integraciones

---

## Resumen

| Change | Fase | Scope (1 línea) | Dep | Gov |
|---|---|---|---|---|
| C-01 | 1 | Compose + skeletons + env + btree_gist | — | BAJO |
| C-02 | 1 | Rol/Usuario(FK)/Paciente/Prof/Sillón + seed | C-01 | CRITICO |
| C-03 | 1 | JWT + RBAC + último-admin + login UI | C-02 | CRITICO |
| C-04 | 2 | Turno + EXCLUDE + agenda + disponibilidad ⭐ | C-02,C-03 | CRITICO |
| C-05 | 2 | Reserva pública + token 1-uso + confirmar | C-04 | MEDIO |
| C-06 | 2 | Worker Redis + recordatorios + webhook mock | C-04 | ALTO |
| C-07 | 2 | Espera 2 h + cascada + conversión | C-04,C-06 | MEDIO |
| C-08 | 3 | HC + FDI 11–48 + catálogo tratamientos | C-02,C-03 | MEDIO |
| C-09 | 3 | Presupuesto desde hallazgos + CC derivada | C-08,C-04 | MEDIO |
| C-10 | 3 | Caja + cierre obligatorio + recibos (simulado) | C-09 | CRITICO |
| C-11 | 3 | OS ficticia + aranceles + liquidación CSV/PDF | C-04,C-09 | MEDIO |
| C-12 | 4 | Usuarios/import/export/seguridad/demo E2E | C-02,C-03 | ALTO |

**Total: 12 changes en 4 fases · 6 GATES · camino crítico 7 changes.**
Excluido v1.0 (post-TP, no generar changes): IA 24/7, portal paciente, MP/AFIP real, perio/imágenes/firma, multi-sede, analytics, API pública, app nativa.
