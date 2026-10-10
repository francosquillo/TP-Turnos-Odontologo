# Graph Report - TP-Turnos-Odontologo  (2026-10-09)

## Corpus Check
- 178 files · ~84,511 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: .gz 4, (none) 3, .example 1)

## Summary
- 1542 nodes · 3022 edges · 104 communities (76 shown, 28 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 263 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7744323b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- app/main.py
- pathlib
- package.json
- App.tsx
- RN-TU-01 choque imposible en DB
- compilerOptions
- Paciente sin cuenta (token 1 uso)
- deps.py
- C-04 agenda core PRIORITARIO
- Compose api+worker+pg16+redis7
- BaseSchema
- test_config.py
- test_compose_config.py
- worker/main.py
- RN-TU-06 espera 2h en cascada
- api-client.ts
- Epica C Clinica
- security.py
- Dueno = alias de Admin (IN-01)
- Stack impuesto por facultad
- vite-env.d.ts
- Fuera de alcance v1.0
- Rol simple por FK (IN-02)
- RN-CO-01 cierre diario obligatorio
- RN-CO-03 saldo derivado
- Flujo 7 auth y sesiones
- modelos/__init__.py
- auth_servicio.py
- disponibilidad.py
- AgendaPro (Generalista)
- CareStack (All-in-one EEUU, top ponderado 4.60, RCM completo)
- Curve Dental (Cloud AWS + IA, booking 24/7)
- DaleControl (MX)
- Dentalink (Regional con localizacion fiscal por pais)
- Dentality (MX multisede, expediente + presupuestos por fases)
- Dentally (UK NHS/UDA, portal + recalls)
- Dentaly (AR)
- DentiDesk (CL multisucursal, convenios, sin sillón)
- Doctoralia (Marketplace + opiniones, techo reputacion)
- Feegow Clinic (BR multidisciplinario, 13 paises)
- Fresha (Marketplace belleza, ref UX reservas)
- Historia Dental (CO barato, CIE-10 + RIPS, agenda debil)
- Simples Dental (BR)
- test_c04_turnos_api.py
- fabricar_usuario
- run_seed
- test_c02_alembic.py
- test_c04_agenda_servicio.py
- AgendaPage.tsx
- agenda_servicio.py
- pytest
- test_c03_auth.py
- db_utils.py
- ADDED Requirements
- Requirements
- turnos.py
- ADDED Requirements
- ADDED Requirements
- Requirements
- Requirements
- test_c04_exclude.py
- PacienteRepository
- ADDED Requirements
- UsuarioRepository
- _app_con
- test_c03_security.py
- test_c02_usuarios_servicio.py
- admin.py
- esquemas/turno.py
- _app_con
- agenda.py
- FakeTurnoRepo
- Decisions
- Decisions
- get_current_user
- TurnoRepository
- UltimoAdminError
- FakeStore
- Decisions
- FakeRepo
- devDependencies
- _TurnoRepoRoto
- Proposal — c-01-foundation-setup (C-01 `foundation-setup`)
- test_crear_usuario_con_rol_valido_persiste
- test_login_401_identico_integracion_pg_redis
- test_env_example.py
- Proposal — c-02-core-models-identidad-pacientes (C-02 `core-models-identidad-pacientes`)
- Proposal — c-04-agenda-turnos-core (C-04 `agenda-turnos-core`)
- Resumen de sesión — 2026-10-06
- test_frontend_shell.py
- Circuito turno-clinica-cobro
- RN-OS-01 validador pre-turno
- test_gitignore.py
- test_worker_docker.py
- 6 diferenciadores v1.0
- RN-CL-04 sin PHI en mensajeria
- manifest.json
- db/__init__.py
- test_requirements_trae_auth_deps
- test_imports_auth_disponibles

## God Nodes (most connected - your core abstractions)
1. `fabricar_usuario()` - 41 edges
2. `FakeRepo` - 36 edges
3. `BaseSchema` - 30 edges
4. `UsuarioRepository` - 29 edges
5. `crear_access_token()` - 26 edges
6. `create_app()` - 25 edges
7. `BaseRepository` - 25 edges
8. `crear_turno()` - 23 edges
9. `Base` - 22 edges
10. `FakeStore` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Migration Plan` --references--> `require_role()`  [INFERRED]
  openspec/changes/archive/2026-10-08-c-03-auth-rbac/design.md → backend/app/core/deps.py
- `Impact` --references--> `require_role()`  [INFERRED]
  openspec/changes/archive/2026-10-08-c-03-auth-rbac/proposal.md → backend/app/core/deps.py
- `New Capabilities` --references--> `require_role()`  [INFERRED]
  openspec/changes/archive/2026-10-08-c-03-auth-rbac/proposal.md → backend/app/core/deps.py
- `D-07 — RBAC: escritura staff, lectura staff; público en C-05` --references--> `require_role()`  [INFERRED]
  openspec/changes/archive/2026-10-09-c-04-agenda-turnos-core/design.md → backend/app/core/deps.py
- `What Changes` --references--> `require_role()`  [INFERRED]
  openspec/changes/archive/2026-10-09-c-04-agenda-turnos-core/proposal.md → backend/app/core/deps.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Circuito turno-clinica-cobro E2E** — knowledge_base_01_vision_y_objetivos_circuito_completo, knowledge_base_07_flujos_principales_f1_reserva, knowledge_base_07_flujos_principales_f3_sillon, knowledge_base_07_flujos_principales_f4_caja, knowledge_base_06_funcionalidades_epica_a_agenda [EXTRACTED 0.85]
- **Camino critico 7 changes** — changes_c01_foundation_setup, changes_c04_agenda_core, changes_c05_reserva_publica, changes_c09_presupuestos_cc, changes_c10_caja_simulada [EXTRACTED 0.90]
- **Garantia anti-solapamiento** — knowledge_base_09_decisiones_dd03_exclude, knowledge_base_05_reglas_de_negocio_rn_tu_01, knowledge_base_04_modelo_de_datos_turno_exclude, changes_c04_agenda_core, discovery_sources_orbita_ficha [INFERRED 0.80]

## Communities (104 total, 28 thin omitted)

### Community 0 - "app/main.py"
Cohesion: 0.07
Nodes (27): C-03: endpoints de sesion (D-01, D-04). Sin rate-limit (D-06, deuda C-12)., clinica_stub(), get, Router stub C-01: clinica (historia/odontograma en C-08)., cobros_stub(), get, Router stub C-01: cobros (caja real en C-09/C-10)., notificaciones_stub() (+19 more)

### Community 1 - "pathlib"
Cohesion: 0.09
Nodes (21): asyncio, do_run_migrations(), C-02 (D-01): env.py async. Engine desde DATABASE_URL del entorno (o…, run_migrations_online(), _necesita_rehash(), Seed idempotente C-02/C-03: roles + admin + demo ficticia (D-04). Guardas por…, True si el hash no es Argon2 (placeholder o bcrypt heredado, C-03)., Task 2.1 GREEN: hace importable el paquete backend/app en tests locales. (+13 more)

### Community 2 - "package.json"
Cohesion: 0.07
Nodes (25): dependencies, react, react-dom, name, private, scripts, build, dev (+17 more)

### Community 3 - "App.tsx"
Cohesion: 0.17
Nodes (12): App(), Barra(), Pagina, PanelAdmin(), raiz, Confirmar(), Login(), Reservas() (+4 more)

### Community 4 - "RN-TU-01 choque imposible en DB"
Cohesion: 0.24
Nodes (10): Reglas duras AGENTS.md, CLAUDE.md mirror de AGENTS.md, Top AR Orbita-DentalSoft-DentiClick, DentalSoft AR (Espejo local), Orbita (AR), Turno anti-solapamiento EXCLUDE, RN-TU-01 choque imposible en DB, RN-TU-02 sobreturno auditado (+2 more)

### Community 5 - "compilerOptions"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+11 more)

### Community 6 - "Paciente sin cuenta (token 1 uso)"
Cohesion: 0.33
Nodes (6): C-05 reserva publica, Paciente sin cuenta (token 1 uso), Rutas publicas + webhook firmado, RN-TU-04 token un solo uso 72h, Flujo 1 reserva + confirmacion, DD-05 paciente sin cuenta

### Community 7 - "deps.py"
Cohesion: 0.11
Nodes (22): AsyncEngine, get_settings(), Task 2.2 GREEN: configuracion solo por env (D-03), fail-fast sin secretos en…, Fabrica sin cache: cada llamada relee el entorno (testeable con monkeypatch)., Settings, get_db(), get_redis(), _obtener_motor() (+14 more)

### Community 8 - "C-04 agenda core PRIORITARIO"
Cohesion: 0.19
Nodes (14): Mapa Change-Skills 12 skills, C-01 foundation archivado, C-02 modelos identidad, C-03 auth + RBAC, C-04 agenda core PRIORITARIO, C-06 notificaciones WhatsApp, C-07 lista de espera loop, C-08 clinica odontograma (+6 more)

### Community 9 - "Compose api+worker+pg16+redis7"
Cohesion: 0.33
Nodes (6): Compose api+worker+pg16+redis7, Datos 100% ficticios, Capas api/servicios/repos, Deploy local Compose, SU-01 sin piloto, ficticio, Spec foundation-setup 6 reqs

### Community 10 - "BaseSchema"
Cohesion: 0.07
Nodes (38): BaseSchema, Esquemas base: estrictos por defecto (extra='forbid', regla dura)., PacienteCreate, PacienteResponse, Esquemas Paciente: estrictos (extra='forbid', D-07)., AgendaConfig, ProfesionalCreate, ProfesionalResponse (+30 more)

### Community 11 - "test_config.py"
Cohesion: 0.12
Nodes (17): test_btree_gist_extension_present(), _importar_config_fresco(), Task 2.2: core/config.py con pydantic-settings, fail-fast, defaults. Orden-…, test_config_defaults(), test_config_falla_sin_database_url(), test_config_falla_sin_jwt_secret(), asyncio, Task 2.3 RED: GET /health 200 / 503 sin secretos, via httpx.AsyncClient. RED… (+9 more)

### Community 12 - "test_compose_config.py"
Cohesion: 0.33
Nodes (7): _load(), Task 1.1 + 1.3 RED: compose con 4 servicios, healthchecks, puertos por env. RED…, test_compose_api_depende_saludable(), test_compose_imagenes_pineadas(), test_compose_tiene_cuatro_servicios(), test_compose_worker_reusa_imagen_api(), yaml

### Community 13 - "worker/main.py"
Cohesion: 0.50
Nodes (4): heartbeat(), main(), Task 2.5 GREEN: worker stub C-01 (jobs reales en C-06). Solo heartbeat., logging

### Community 14 - "RN-TU-06 espera 2h en cascada"
Cohesion: 0.29
Nodes (7): NexHealth (Capa sobre PMS), WhatsApp Business API, EsperaEntry ventana 2h, RN-NO-01 recordatorios 48/24h, RN-TU-06 espera 2h en cascada, Epica B WhatsApp, Flujo 6 lista de espera loop

### Community 15 - "api-client.ts"
Cohesion: 0.14
Nodes (24): conBearer(), definirAccess(), esHealthStatus(), esMeRespuesta(), esTokenRespuesta(), fetchConAuth(), fetchHealth(), HealthStatus (+16 more)

### Community 16 - "Epica C Clinica"
Cohesion: 0.40
Nodes (6): Odontograma FDI 11-48 + caras, Presupuesto nace de hallazgo, RN-CL-01 presupuesto desde odontograma, RN-GL-01 soft-delete, Epica C Clinica, Flujo 3 atencion en sillon

### Community 17 - "security.py"
Cohesion: 0.18
Nodes (11): Exception, C-03: hash Argon2id + JWT HS256 (reemplaza el stub C-01). D-02: `pwdlib`…, Access JWT ausente o ilegible (se mapea a 401)., El `exp` quedo atras incluso con leeway (se mapea a 401)., TokenError, TokenExpiradoError, jwt, pwdlib (+3 more)

### Community 18 - "Dueno = alias de Admin (IN-01)"
Cohesion: 0.50
Nodes (4): Dueno = alias de Admin (IN-01), RN-AU-03 resguardo ultimo admin, Epica F Administracion, IN-01 Dueno=Admin resuelta

### Community 19 - "Stack impuesto por facultad"
Cohesion: 0.67
Nodes (3): Requirements FastAPI/SQLAlchemy, Monolito modular + SPA, Stack impuesto por facultad

### Community 21 - "Fuera de alcance v1.0"
Cohesion: 0.67
Nodes (3): Fuera de alcance v1.0, Pagos simulados, AFIP post-TP, Sillon sede unica extensible

### Community 22 - "Rol simple por FK (IN-02)"
Cohesion: 0.67
Nodes (3): RBAC 3 roles fijos, Rol simple por FK (IN-02), IN-02 rol FK resuelta

### Community 23 - "RN-CO-01 cierre diario obligatorio"
Cohesion: 0.67
Nodes (3): Caja cierre diario + recibo secuencial, RN-CO-01 cierre diario obligatorio, Epica D Cobros y caja

### Community 24 - "RN-CO-03 saldo derivado"
Cohesion: 0.67
Nodes (3): Cuenta corriente saldo derivado, RN-CO-03 saldo derivado, Flujo 4 cobro y cierre

### Community 29 - "modelos/__init__.py"
Cohesion: 0.14
Nodes (14): C-02: Base declarativa + entidades (D-05: tipos Postgres estrictos). PK BIGINT…, BaseRepository, AsyncSession, Base repository generico async (D-02): get/list/crear/actualizar/eliminar. Los…, CRUD async tipado por entidad; los repos finos heredan sin duplicar., Repos C-02: base generica + finos por entidad (D-02)., Repo Paciente: hereda CRUD + baja logica (RN-GL-01, D-06)., Repo Profesional: hereda CRUD de la base (D-02). (+6 more)

### Community 30 - "auth_servicio.py"
Cohesion: 0.08
Nodes (46): _cookie_segura(), login(), logout(), JSONResponse, post, RepoDep, Emite access (cuerpo) + refresh (cookie httpOnly); resto -> 401/503., Rota el par (GETDEL+SET); reuso/ausente/vencido -> 401 sin emitir. (+38 more)

### Community 31 - "disponibilidad.py"
Cohesion: 0.20
Nodes (10): datetime, get, LecturaDep, ProfesionalRepoDep, SillonRepoDep, TurnoRepoDep, GET /disponibilidad: huecos = agenda_config − turnos activos (C-04, D-04).…, Huecos ofrecibles del profesional en [desde, hasta). (+2 more)

### Community 47 - "test_c04_turnos_api.py"
Cohesion: 0.08
Nodes (39): get_paciente_repo(), get_profesional_repo(), get_sillon_repo(), get_turno_repo(), DbDep, get_usuario_repo(), DbDep, Repo usuarios sobre la sesion del request (mockeable en tests). (+31 more)

### Community 48 - "fabricar_usuario"
Cohesion: 0.08
Nodes (41): Factoria de guard por rol (D-03): 403 si el rol no esta incluido. Uso:…, require_role(), crear_access_token(), hashear_password(), Hashea con Argon2id (todo hash nuevo sale `$argon2id$`)., Firma HS256 con claims sub/rol/iat/exp (UTC, exp=+JWT_EXPIRE_MIN)., fabricar_usuario(), SimpleNamespace (+33 more)

### Community 49 - "run_seed"
Cohesion: 0.06
Nodes (40): main(), AsyncSession, Orden roles -> admin -> demo, con commit unico. Fail-fast sin password., Entry CLI: python -m app.db.seed (cwd=backend)., Crea los 3 roles fijos si faltan (Dueño=alias de Admin, sin tabla extra)., Crea el admin inicial si falta; re-hashea a Argon2 si es heredado., Sillon + profesional demo con agenda_config semanal valida., run_seed() (+32 more)

### Community 50 - "test_c02_alembic.py"
Cohesion: 0.08
Nodes (38): dsn_test(), _engine_or_skip(), pg_reachable(), DSN del Postgres real de compose (override via DATABASE_URL_TEST)., Chequeo liviano via asyncpg (evita warnings de Alembic al skipear)., Reset idempotente antes del ciclo upgrade/downgrade (C-02, C-04). La suite…, reset_estado_base(), asyncio (+30 more)

### Community 51 - "test_c04_agenda_servicio.py"
Cohesion: 0.11
Nodes (37): crear_turno(), EntidadNoEncontradaError, HuecoOcupadoError, LookupError, Crea un turno validando FKs, fin>inicio, pasado y solapamiento (D-02)., Solapamiento sin sobreturno valido (se mapea a 409 con alternativas)., FK inexistente (se mapea a 422)., _integrity_falso() (+29 more)

### Community 52 - "AgendaPage.tsx"
Cohesion: 0.14
Nodes (29): AgendaPage(), hoyLocal(), cambiarEstadoTurno(), ConflictoHuecoError, crearTurno(), CrearTurnoDatos, esHueco(), esTurno() (+21 more)

### Community 53 - "agenda_servicio.py"
Cohesion: 0.10
Nodes (35): _a_hora(), _alternativas_ante_conflicto(), calcular_huecos(), cambiar_estado(), _codigo_integridad(), _es_violacion_exclude(), _es_violacion_fk(), MotivoRequeridoError (+27 more)

### Community 54 - "pytest"
Cohesion: 0.12
Nodes (22): Base, Base declarativa unica: target_metadata de Alembic (D-01)., Paciente: soft-delete via deleted_at (RN-GL-01, D-06)., Profesional: vinculo opcional a cuenta + agenda_config JSONB (D-05)., Rol: 3 fijos (admin/odontologo/secretaria). NUNCA rol dueno (IN-01)., Rol, Sillon: sede texto libre, default sede unica v1.0 (extensible post-TP)., Turno: agenda core con doble anti-solapamiento a nivel DB (C-04, D-01). Dos… (+14 more)

### Community 55 - "test_c03_auth.py"
Cohesion: 0.13
Nodes (32): LoginIn, MeOut, Esquemas /auth: estrictos (extra='forbid'), sin hash en ningun response., TokenOut, _app_con_fakes(), _ejemplo(), _login_y_refresh(), asyncio (+24 more)

### Community 56 - "db_utils.py"
Cohesion: 0.08
Nodes (26): ProfesionalRepository, AsyncSession, Profesional vinculado a la cuenta (RBAC odontologo, D-07)., AsyncSession, RolRepository, AsyncSession, SillonRepository, Helper C-02: sesiones contra Postgres REAL (NUNCA SQLite). Patron heredado de… (+18 more)

### Community 57 - "ADDED Requirements"
Cohesion: 0.06
Nodes (31): ADDED Requirements, Purpose, Requirement: Agenda por vistas día/semana/mes, Requirement: Columna token reservada sin flujo en este change, Requirement: CRUD de turnos con esquemas estrictos y RBAC staff, Requirement: Disponibilidad como horario menos turnos con 409 y re-oferta, Requirement: Modelo Turno con doble anti-solapamiento a nivel DB, Requirement: Máquina de estados con transiciones cerradas y cancelación motivada (+23 more)

### Community 58 - "Requirements"
Cohesion: 0.06
Nodes (31): agenda-turnos-core Specification, Purpose, Requirement: Agenda por vistas día/semana/mes, Requirement: Columna token reservada sin flujo en este change, Requirement: CRUD de turnos con esquemas estrictos y RBAC staff, Requirement: Disponibilidad como horario menos turnos con 409 y re-oferta, Requirement: Modelo Turno con doble anti-solapamiento a nivel DB, Requirement: Máquina de estados con transiciones cerradas y cancelación motivada (+23 more)

### Community 59 - "turnos.py"
Cohesion: 0.15
Nodes (29): _a_out(), cambiar_estado(), _conflicto(), crear_turno(), _es_admin(), _es_odontologo(), listar_turnos(), obtener_turno() (+21 more)

### Community 60 - "ADDED Requirements"
Cohesion: 0.07
Nodes (27): ADDED Requirements, Purpose, Requirement: Base repository genérico async, Requirement: Migración 001 reproducible con convenciones Postgres estrictas, Requirement: Paciente con CRUD, índices y soft-delete, Requirement: Profesional con agenda semanal configurable, Requirement: Roles fijos con alias Dueño=Admin, Requirement: Seed demo idempotente con datos ficticios (+19 more)

### Community 61 - "ADDED Requirements"
Cohesion: 0.07
Nodes (27): ADDED Requirements, Purpose, Requirement: Access JWT corto y hash Argon2, Requirement: Autorización por rol con require_role y matriz 03, Requirement: Login con 401 genérico sin enumerar usuarios, Requirement: Refresh rotativo con invalidación del anterior, Requirement: Resguardo del último admin expuesto vía HTTP, Requirement: Sesión actual y logout con invalidación (+19 more)

### Community 62 - "Requirements"
Cohesion: 0.07
Nodes (27): auth-rbac Specification, Purpose, Requirement: Access JWT corto y hash Argon2, Requirement: Autorización por rol con require_role y matriz 03, Requirement: Login con 401 genérico sin enumerar usuarios, Requirement: Refresh rotativo con invalidación del anterior, Requirement: Resguardo del último admin expuesto vía HTTP, Requirement: Sesión actual y logout con invalidación (+19 more)

### Community 63 - "Requirements"
Cohesion: 0.07
Nodes (27): core-models-identidad-pacientes Specification, Purpose, Requirement: Base repository genérico async, Requirement: Migración 001 reproducible con convenciones Postgres estrictas, Requirement: Paciente con CRUD, índices y soft-delete, Requirement: Profesional con agenda semanal configurable, Requirement: Roles fijos con alias Dueño=Admin, Requirement: Seed demo idempotente con datos ficticios (+19 more)

### Community 64 - "test_c04_exclude.py"
Cohesion: 0.14
Nodes (26): Paciente, Profesional, Sillon, Turno, _es_violacion_exclusion(), asyncio, Exception, C-04 task 1.3: EXCLUDE a nivel DB contra Postgres REAL (nunca SQLite). Inserts… (+18 more)

### Community 65 - "PacienteRepository"
Cohesion: 0.12
Nodes (20): PacienteRepository, AsyncSession, asyncio, C-02 tasks 3.1-3.3: Paciente (CRUD + soft-delete + DNI) contra PG real., Task 3.1 GREEN: crear/leer/actualizar paciente ficticio., Task 3.2 GREEN: eliminado no lista pero la fila persiste con deleted_at., Task 3.3 GREEN: mismo DNI -> IntegrityError; dos NULL -> ok., test_crud_paciente_ficticio_ok() (+12 more)

### Community 66 - "ADDED Requirements"
Cohesion: 0.10
Nodes (20): ADDED Requirements, Purpose, Requirement: Backend skeleton por capas con healthcheck, Requirement: Compose local con cuatro servicios, Requirement: Configuración solo por entorno, Requirement: Extensión btree_gist habilitada, Requirement: Frontend shell Vite React TS estricto, Requirement: Tests base de infraestructura (+12 more)

### Community 67 - "UsuarioRepository"
Cohesion: 0.15
Nodes (15): AsyncSession, Admins activos (para el guard >=1 admin)., Usuario por id con rol cargado (auth necesita `usuario.rol.nombre`)., Listado admin con rol cargado, orden estable por id., UsuarioRepository, desactivar_usuario(), eliminar_usuario(), _es_admin_activo() (+7 more)

### Community 68 - "_app_con"
Cohesion: 0.13
Nodes (17): Task 6.1: seed demo valida y da 16 huecos el lunes (fijado para C-05)., test_agenda_config_demo_parsea(), _app_con(), _bearer(), _db(), _profesional_demo(), asyncio, Task 4.1 RED: martes sin horario -> [] (nunca huecos inventados). (+9 more)

### Community 69 - "test_c03_security.py"
Cohesion: 0.18
Nodes (18): Firma incorrecta, claims rotos o formato ilegible (se mapea a 401)., Verifica contra Argon2 o bcrypt heredado; basura/incorrecta -> False., Verifica firma + exp (leeway 30 s); expirado -> TokenExpiradoError., TokenInvalidoError, verificar_access_token(), verificar_password(), C-03 task 1.1 RED: dependencias de auth en requirements.txt., Task 1.2 RED: hash nuevo es Argon2id y verifica (ok y mala). (+10 more)

### Community 70 - "test_c02_usuarios_servicio.py"
Cohesion: 0.18
Nodes (17): asyncio, C-02 task 2.3: guard ultimo-admin a nivel servicio (RN-AU-03). Unit con repos…, Task 2.3 integracion PG: el admin sigue activo tras el bloqueo., Task 2.3 RED->GREEN: desactivar al unico admin activo aborta., Triangulacion: con 2 admins activos, desactivar uno funciona., Triangulacion: desactivar secretaria no consulta admins., Task 2.3: eliminar al unico admin activo aborta., Triangulacion: id inexistente -> UsuarioNoEncontradoError. (+9 more)

### Community 71 - "admin.py"
Cohesion: 0.18
Nodes (16): AdminDep, _a_out(), desactivar(), eliminar(), listar_usuarios(), get, patch, RepoDep (+8 more)

### Community 72 - "esquemas/turno.py"
Cohesion: 0.18
Nodes (13): EstadoPatch, Esquemas Turno: estrictos (extra='forbid', regla dura). Sin token (D-05)., ReprogramarIn, TurnoIn, C-04 task 3.1: esquemas Turno estrictos (extra='forbid', fin>inicio)., Task 3.1 RED: campo extra -> 422 (extra='forbid')., Triangulacion: fin<=inicio -> 422 en esquema y reprogramacion., Triangulacion: TurnoOut sin token; EstadoPatch acepta motivo. (+5 more)

### Community 73 - "_app_con"
Cohesion: 0.17
Nodes (15): _app_con(), _db(), _cuerpo(), asyncio, Task 3.2 RED: solape -> 409 con alternativas no vacias., Task 3.2 RED: sin Bearer -> 401; odontologo no puede crear -> 403., Triangulacion: extra -> 422; pasado secretaria 422 pero admin 201., Task 3.4 RED: mover a hueco ocupado -> 409 y horario original intacto. (+7 more)

### Community 74 - "agenda.py"
Cohesion: 0.13
Nodes (12): date, get, LecturaDep, PacienteRepoDep, ProfesionalRepoDep, SillonRepoDep, TurnoRepoDep, GET /agenda: turnos del periodo por vista dia|semana|mes (C-04, US-001). RBAC… (+4 more)

### Community 75 - "FakeTurnoRepo"
Cohesion: 0.20
Nodes (8): _chocan(), _es_activo(), fabricar_entidad(), FakeTurnoRepo, datetime, SimpleNamespace, Fakes C-04: repos en memoria para servicio y HTTP sin PG (patron c03_fakes).…, TurnoRepository en memoria (misma interfaz usada por el servicio).

### Community 76 - "Decisions"
Cohesion: 0.12
Nodes (15): Context, D-01 — Doble EXCLUDE parcial: solo turnos activos no-sobreturno participan, D-02 — Sobreturno = flag + motivo obligatorio + auditoría, nunca constraint roto, D-03 — Máquina de estados cerrada con transiciones explícitas, D-04 — Disponibilidad = horario semanal de `agenda_config` − turnos activos, D-05 — Columna token reservada ahora, flujo token en C-05, D-06 — Reprogramar revalida como creación; colisión → 409 + re-oferta, D-07 — RBAC: escritura staff, lectura staff; público en C-05 (+7 more)

### Community 77 - "Decisions"
Cohesion: 0.14
Nodes (13): Context, D-01 — Compose con 4 servicios, imágenes pineadas, red única, healthchecks, D-02 — Backend `backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}` + `core/` + `main.py`, D-03 — Config solo env + `.env.example` versionado, `.env` ignorado, D-04 — `btree_gist` vía init SQL versionado, no manual, D-05 — Frontend Vite + React 18 + TS 5 estricto, shell mínimo, D-06 — Tests base con Postgres/Redis reales vía compose, pytest + Vitest smoke, Decisions (+5 more)

### Community 78 - "get_current_user"
Cohesion: 0.15
Nodes (12): get_current_user(), RepoDep, Identidad del Bearer (401 sin/invalido/expirado/inactivo). `async def` porque…, BearerDep, Capabilities, Impact, Leer antes (fuente de verdad), Modified Capabilities (+4 more)

### Community 79 - "TurnoRepository"
Cohesion: 0.22
Nodes (8): AsyncSession, datetime, Turnos activos que pisan [desde, hasta), ordenados por inicio., True si algun activo no-sobreturno choca por profesional o sillon., Turnos del periodo para vistas de agenda (incluye cancelados si se pide)., TurnoRepository, Task 2.1 RED: los selects del repo compilan sin PG (caza typos)., test_repo_consultas_compilan_en_postgres()

### Community 80 - "UltimoAdminError"
Cohesion: 0.17
Nodes (10): Lookup case-insensitive (usa uq_usuario_email_lower), con rol., Exception, Se intento dejar el sistema sin admins activos., UltimoAdminError, Context, Design — c-03-auth-rbac, Goals / Non-Goals, Migration Plan (+2 more)

### Community 81 - "FakeStore"
Cohesion: 0.18
Nodes (5): FakeStore, Fakes C-03: store Redis en memoria + repo usuarios en memoria. Los tests HTTP…, SesionStore en memoria con expiracion (ex en segundos)., time, types

### Community 82 - "Decisions"
Cohesion: 0.18
Nodes (11): me(), get, Identidad del Bearer (cualquier rol autenticado, nunca el hash)., CurrentUserDep, D-01 — Access JWT HS256 corto + refresh opaco en Redis (vs refresh JWT con denylist), D-02 — Argon2id primario, bcrypt solo verificación heredada (vs solo bcrypt), D-03 — `require_role(*roles)` como factoría sobre `get_current_user`, D-05 — Reuso de refresh = robo probable: invalida la familia (+3 more)

### Community 84 - "devDependencies"
Cohesion: 0.18
Nodes (11): devDependencies, jsdom, @testing-library/jest-dom, @testing-library/react, @testing-library/user-event, @types/react, @types/react-dom, typescript (+3 more)

### Community 85 - "_TurnoRepoRoto"
Cohesion: 0.22
Nodes (5): _OrigenRoto, Exception, IntegrityError.orig falso con pgcode/sqlstate y mensaje realista., TurnoRepository falso cuyo crear() lanza el IntegrityError dado., _TurnoRepoRoto

### Community 86 - "Proposal — c-01-foundation-setup (C-01 `foundation-setup`)"
Cohesion: 0.22
Nodes (8): Capabilities, Impact, Leer antes (fuente de verdad), Modified Capabilities, New Capabilities, Proposal — c-01-foundation-setup (C-01 `foundation-setup`), What Changes, Why

### Community 87 - "test_crear_usuario_con_rol_valido_persiste"
Cohesion: 0.25
Nodes (8): asyncio, Task 2.1 GREEN: usuario con rol secretaria persiste activo y con tz., Spec: nombre de rol fuera del catalogo viola CHECK (sin rol dueno)., FK rol simple: rol_id inexistente viola la FK., test_crear_usuario_con_rol_valido_persiste(), test_rol_fuera_de_catalogo_rechazado(), test_usuario_sin_rol_valido_rechazado(), 2. Rol + Usuario (identidad, FK simple)

### Community 88 - "test_login_401_identico_integracion_pg_redis"
Cohesion: 0.32
Nodes (7): Task 2.2 integracion: login real emite access + cookie., Task 2.2 integracion: inexistente vs mala password, mismo 401., _redis_real_o_skip(), _sembrar_usuario_pg(), test_login_401_identico_integracion_pg_redis(), test_login_ok_integracion_pg_redis(), _db()

### Community 89 - "test_env_example.py"
Cohesion: 0.25
Nodes (4): Task 3.1 RED: .env.example completo con placeholders, sin secretos reales., C-03 task 5.1 RED: REFRESH_EXPIRE_DAYS con default 7 documentado., test_env_example_trae_refresh_expire(), 5. Verificación integral GATE 2

### Community 90 - "Proposal — c-02-core-models-identidad-pacientes (C-02 `core-models-identidad-pacientes`)"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Leer antes (fuente de verdad), Modified Capabilities, New Capabilities, Proposal — c-02-core-models-identidad-pacientes (C-02 `core-models-identidad-pacientes`), Why

### Community 91 - "Proposal — c-04-agenda-turnos-core (C-04 `agenda-turnos-core`)"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Leer antes (fuente de verdad), New Capabilities, Proposal — c-04-agenda-turnos-core (C-04 `agenda-turnos-core`), What Changes, Why

### Community 92 - "Resumen de sesión — 2026-10-06"
Cohesion: 0.25
Nodes (7): Archivos relevantes, Descubrimientos, Instrucciones / preferencias del usuario, Logrado, Objetivo, Próximos pasos, Resumen de sesión — 2026-10-06

### Community 94 - "Circuito turno-clinica-cobro"
Cohesion: 0.33
Nodes (6): Problema: circuito incompleto, Frontend Vite React TS shell, Circuito turno-clinica-cobro, Prioridad Turnos/Agenda A+B, Epica A Agenda prioritaria, KB README indice + quickstart

### Community 95 - "RN-OS-01 validador pre-turno"
Cohesion: 0.33
Nodes (6): DentiClick (AR), Dentrix Ascend (EEUU cloud + Eligibility pre-turno), Nomenclador versionado por vigencia, RN-OS-01 validador pre-turno, Epica E Obras sociales, Flujo 5 liquidacion OS

### Community 98 - "6 diferenciadores v1.0"
Cohesion: 0.40
Nodes (5): MVP doble pista sugerido, Vacios: seguridad sin evidencia, Tab32 (EEUU), 6 diferenciadores v1.0, DD-06 MVP doble pista

### Community 99 - "RN-CL-04 sin PHI en mensajeria"
Cohesion: 0.40
Nodes (5): Open Dental (PMS profundo, ASAP anti-huecos, tabla cifrado honesta), Notificacion sin PHI + costo Meta, RN-CL-04 sin PHI en mensajeria, Flujo 2 recordatorios async, Worker + cola Redis

## Ambiguous Edges - Review These
- `Frontend Vite React TS shell` → `Epica A Agenda prioritaria`  [AMBIGUOUS]
  frontend/index.html · relation: conceptually_related_to

## Knowledge Gaps
- **300 isolated node(s):** `version`, `chunks`, `name`, `private`, `version` (+295 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 760 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Frontend Vite React TS shell` and `Epica A Agenda prioritaria`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `RequireRole()` connect `App.tsx` to `Requirements`, `ADDED Requirements`, `get_current_user`, `api-client.ts`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Why does `What Changes` connect `get_current_user` to `UltimoAdminError`, `App.tsx`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `require_role()` connect `fabricar_usuario` to `deps.py`, `Proposal — c-04-agenda-turnos-core (C-04 `agenda-turnos-core`)`, `Decisions`, `get_current_user`, `test_c04_turnos_api.py`, `UltimoAdminError`, `Decisions`, `ADDED Requirements`, `Requirements`, `turnos.py`?**
  _High betweenness centrality (0.095) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `FakeRepo` (e.g. with `test_login_email_inexistente_y_password_mala_mismo_401()` and `test_login_in_rechaza_campo_extra_422()`) actually correct?**
  _`FakeRepo` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `BaseSchema` (e.g. with `test_esquema_base_rechaza_campos_extra()` and `test_payload_extra_retorna_422()`) actually correct?**
  _`BaseSchema` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `version`, `chunks`, `name` to the rest of the system?**
  _300 weakly-connected nodes found - possible documentation gaps or missing edges._