# Graph Report - TP-Turnos-Odontologo  (2026-10-05)

## Corpus Check
- Corpus is ~44,510 words - fits in a single context window. You may not need a graph.

## Summary
- 349 nodes · 396 edges · 47 communities (23 shown, 24 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 14 edges (avg confidence: 0.77)
- Token cost: 55,727 input · 0 output

## Community Hubs (Navigation)
- API Router Stubs
- TDD Test Suite
- Frontend Dependencies
- SPA Pages Shell
- Obras Sociales Domain
- TypeScript Strict Config
- Online Booking Vision
- Env Config Core
- Change Roadmap Chain
- Foundation and Design
- App Bootstrap Health
- Strict Schemas Base
- Compose Contract Tests
- Worker Heartbeat Stub
- Waitlist Loop
- Typed API Client
- Odontograma Budgets Flow
- JWT Stub
- Owner Admin Alias
- Imposed Stack
- Vite Env Types
- Out of Scope
- Simple Role FK
- Daily Cash Close
- Derived Balance Account
- Auth Sessions Flow
- Generalist Booking Reference
- US Market Leader
- Cloud Booking Suite
- Imaging Value Suite
- Fiscal Localization Suite
- Mexican Multisite Suite
- NHS Portal Model
- Local Odontogram Rival
- Chilean Multisite Suite
- Reputation Marketplace
- Brazilian Multispecialty Suite
- Booking UX Reference
- Budget Colombian Suite
- Brazilian Payments Suite

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 18 edges
2. `C-04 agenda core PRIORITARIO` - 9 edges
3. `get_settings()` - 8 edges
4. `App()` - 7 edges
5. `RN-TU-01 choque imposible en DB` - 7 edges
6. `create_app()` - 6 edges
7. `BaseSchema` - 5 edges
8. `_load()` - 5 edges
9. `scripts` - 5 edges
10. `Compose api+worker+pg16+redis7` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Config + restricciones vinculantes` --semantically_similar_to--> `Reglas duras AGENTS.md`  [INFERRED] [semantically similar]
  openspec/config.yaml → AGENTS.md
- `Frontend Vite React TS shell` --conceptually_related_to--> `Epica A Agenda prioritaria`  [AMBIGUOUS]
  frontend/index.html → knowledge-base/06_funcionalidades.md
- `Capas api/servicios/repos` --conceptually_related_to--> `Compose api+worker+pg16+redis7`  [INFERRED]
  knowledge-base/08_arquitectura_propuesta.md → docker-compose.yml
- `Plazo duro 12/10/2026` --conceptually_related_to--> `Camino critico 7 changes`  [INFERRED]
  knowledge-base/01_vision_y_objetivos.md → CHANGES.md
- `C-04 agenda core PRIORITARIO` --references--> `RN-TU-01 choque imposible en DB`  [EXTRACTED]
  CHANGES.md → knowledge-base/05_reglas_de_negocio.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Circuito turno-clinica-cobro E2E** — knowledge_base_01_vision_y_objetivos_circuito_completo, knowledge_base_07_flujos_principales_f1_reserva, knowledge_base_07_flujos_principales_f3_sillon, knowledge_base_07_flujos_principales_f4_caja, knowledge_base_06_funcionalidades_epica_a_agenda [EXTRACTED 0.85]
- **Camino critico 7 changes** — changes_c01_foundation_setup, changes_c04_agenda_core, changes_c05_reserva_publica, changes_c09_presupuestos_cc, changes_c10_caja_simulada [EXTRACTED 0.90]
- **Garantia anti-solapamiento** — knowledge_base_09_decisiones_dd03_exclude, knowledge_base_05_reglas_de_negocio_rn_tu_01, knowledge_base_04_modelo_de_datos_turno_exclude, changes_c04_agenda_core, discovery_sources_orbita_ficha [INFERRED 0.80]

## Communities (47 total, 24 thin omitted)

### Community 0 - "API Router Stubs"
Cohesion: 0.06
Nodes (35): admin_stub(), get, Router stub C-01: admin (panel real post C-03)., auth_stub(), get, Router stub C-01: auth (JWT real en C-03)., clinica_stub(), get (+27 more)

### Community 1 - "TDD Test Suite"
Cohesion: 0.05
Nodes (19): Task 2.1 GREEN: hace importable el paquete backend/app en tests locales., asyncio, Task 1.2 RED: init SQL btree_gist presente + test integracion contra Postgres…, Integracion: requiere Postgres real del compose (NUNCA SQLite)., test_btree_gist_extension_en_postgres_real(), Task 3.1 RED: .env.example completo con placeholders, sin secretos reales., Task 4.1-4.3 RED: scaffold Vite+React+TS estricto, api-client, auth-context,…, Task 3.2 RED: .env ignorado, .env.example trackeable. (+11 more)

### Community 2 - "Frontend Dependencies"
Cohesion: 0.06
Nodes (31): dependencies, react, react-dom, devDependencies, jsdom, @testing-library/jest-dom, @testing-library/react, @types/react (+23 more)

### Community 3 - "SPA Pages Shell"
Cohesion: 0.15
Nodes (13): App(), Pagina, raiz, Confirmar(), Reservas(), Seguridad(), AuthContexto, AuthProveedor() (+5 more)

### Community 4 - "Obras Sociales Domain"
Cohesion: 0.11
Nodes (20): Reglas duras AGENTS.md, CLAUDE.md mirror de AGENTS.md, Top AR Orbita-DentalSoft-DentiClick, DentalSoft AR (Espejo local), DentiClick (AR), Dentrix Ascend (EEUU cloud + Eligibility pre-turno), Open Dental (PMS profundo, ASAP anti-huecos, tabla cifrado honesta), Orbita (AR) (+12 more)

### Community 5 - "TypeScript Strict Config"
Cohesion: 0.10
Nodes (19): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+11 more)

### Community 6 - "Online Booking Vision"
Cohesion: 0.12
Nodes (17): C-05 reserva publica, MVP doble pista sugerido, Problema: circuito incompleto, Vacios: seguridad sin evidencia, Tab32 (EEUU), Frontend Vite React TS shell, Circuito turno-clinica-cobro, Prioridad Turnos/Agenda A+B (+9 more)

### Community 7 - "Env Config Core"
Cohesion: 0.18
Nodes (12): get_settings(), Task 2.2 GREEN: configuracion solo por env (D-03), fail-fast sin secretos en…, Fabrica sin cache: cada llamada relee el entorno (testeable con monkeypatch)., Settings, Dependencias reutilizables con Annotated (nunca `...` como default)., check_postgres(), check_redis(), Ping Postgres real; nunca levanta excepcion (retorna 'down'). (+4 more)

### Community 8 - "Change Roadmap Chain"
Cohesion: 0.21
Nodes (13): Mapa Change-Skills 12 skills, C-02 modelos identidad, C-03 auth + RBAC, C-04 agenda core PRIORITARIO, C-06 notificaciones WhatsApp, C-07 lista de espera loop, C-08 clinica odontograma, C-09 presupuestos + CC (+5 more)

### Community 9 - "Foundation and Design"
Cohesion: 0.21
Nodes (12): C-01 foundation archivado, Compose api+worker+pg16+redis7, Datos 100% ficticios, Capas api/servicios/repos, Deploy local Compose, DD-03 EXCLUDE en DB, SU-01 sin piloto, ficticio, Archived spec mirror (6 reqs) (+4 more)

### Community 10 - "App Bootstrap Health"
Cohesion: 0.25
Nodes (8): BaseSchema, create_app(), asyncio, Task 3.3 RED: CORS por env + extra='forbid' (422 ante campo extra)., test_cors_origen_no_permitido_rechazado(), test_esquema_base_rechaza_campos_extra(), test_payload_extra_retorna_422(), BaseModel

### Community 11 - "Strict Schemas Base"
Cohesion: 0.27
Nodes (8): Esquemas base: estrictos por defecto (extra='forbid', regla dura)., _importar_config_fresco(), Task 2.2: core/config.py con pydantic-settings, fail-fast, defaults. Orden-…, test_config_defaults(), test_config_falla_sin_database_url(), test_config_falla_sin_jwt_secret(), importlib, pydantic

### Community 12 - "Compose Contract Tests"
Cohesion: 0.33
Nodes (7): _load(), Task 1.1 + 1.3 RED: compose con 4 servicios, healthchecks, puertos por env. RED…, test_compose_api_depende_saludable(), test_compose_imagenes_pineadas(), test_compose_tiene_cuatro_servicios(), test_compose_worker_reusa_imagen_api(), yaml

### Community 13 - "Worker Heartbeat Stub"
Cohesion: 0.33
Nodes (6): asyncio, test_import_smoke_main(), heartbeat(), main(), Task 2.5 GREEN: worker stub C-01 (jobs reales en C-06). Solo heartbeat., logging

### Community 14 - "Waitlist Loop"
Cohesion: 0.29
Nodes (7): NexHealth (Capa sobre PMS), WhatsApp Business API, EsperaEntry ventana 2h, RN-NO-01 recordatorios 48/24h, RN-TU-06 espera 2h en cascada, Epica B WhatsApp, Flujo 6 lista de espera loop

### Community 15 - "Typed API Client"
Cohesion: 0.47
Nodes (4): ApiError, esHealthStatus(), fetchHealth(), HealthStatus

### Community 16 - "Odontograma Budgets Flow"
Cohesion: 0.40
Nodes (6): Odontograma FDI 11-48 + caras, Presupuesto nace de hallazgo, RN-CL-01 presupuesto desde odontograma, RN-GL-01 soft-delete, Epica C Clinica, Flujo 3 atencion en sillon

### Community 18 - "Owner Admin Alias"
Cohesion: 0.50
Nodes (4): Dueno = alias de Admin (IN-01), RN-AU-03 resguardo ultimo admin, Epica F Administracion, IN-01 Dueno=Admin resuelta

### Community 19 - "Imposed Stack"
Cohesion: 0.67
Nodes (3): Requirements FastAPI/SQLAlchemy, Monolito modular + SPA, Stack impuesto por facultad

### Community 21 - "Out of Scope"
Cohesion: 0.67
Nodes (3): Fuera de alcance v1.0, Pagos simulados, AFIP post-TP, Sillon sede unica extensible

### Community 22 - "Simple Role FK"
Cohesion: 0.67
Nodes (3): RBAC 3 roles fijos, Rol simple por FK (IN-02), IN-02 rol FK resuelta

### Community 23 - "Daily Cash Close"
Cohesion: 0.67
Nodes (3): Caja cierre diario + recibo secuencial, RN-CO-01 cierre diario obligatorio, Epica D Cobros y caja

### Community 24 - "Derived Balance Account"
Cohesion: 0.67
Nodes (3): Cuenta corriente saldo derivado, RN-CO-03 saldo derivado, Flujo 4 cobro y cierre

## Ambiguous Edges - Review These
- `Epica A Agenda prioritaria` → `Frontend Vite React TS shell`  [AMBIGUOUS]
  frontend/index.html · relation: conceptually_related_to

## Knowledge Gaps
- **105 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+100 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 192 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Epica A Agenda prioritaria` and `Frontend Vite React TS shell`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `RN-TU-01 choque imposible en DB` connect `Obras Sociales Domain` to `Change Roadmap Chain`, `Foundation and Design`, `Online Booking Vision`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `test_import_smoke_main()` connect `Worker Heartbeat Stub` to `TDD Test Suite`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _105 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `API Router Stubs` be split into smaller, more focused modules?**
  _Cohesion score 0.05551020408163265 - nodes in this community are weakly interconnected._
- **Should `TDD Test Suite` be split into smaller, more focused modules?**
  _Cohesion score 0.0507399577167019 - nodes in this community are weakly interconnected._
- **Should `Frontend Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.0625 - nodes in this community are weakly interconnected._