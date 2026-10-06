# Skill Registry — TP-Turnos-Odontologo

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

Stack: Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis + Docker/Compose; React + TypeScript + Vite. Equipo 3, plazo 12/10/2026, sede única, pagos simulados, OS ficticia, deploy local. Fuente de verdad: `knowledge-base/` + `CHANGES.md` (12 changes, 6 gates).

## User Skills

| Trigger | Skill | Path | Changes / Fases en este proyecto |
|---------|-------|------|----------------------------------|
| FastAPI APIs, Pydantic models, dependencies, SSE, serving frontend apps | fastapi | C:\Users\ingra\.agents\skills\fastapi\SKILL.md | Todos C-01→C-12 (core backend). C-01 skeleton/routers; C-03 `require_role(...)`; C-04→C-12 endpoints |
| Building new FastAPI applications or setting up backend API projects | fastapi-templates | C:\Users\ingra\.agents\skills\fastapi-templates\SKILL.md | C-01 (estructura `api/servicios/repos/modelos/esquemas/worker/tests`, DI, async, `.env.example`); C-02 repos SQLAlchemy 2 async |
| Writing/changing anything in Postgres: tables, columns, schema, migrations, RLS, indexes, triggers, functions, queues/jobs, pgvector, pg_restore; diagnosing slow queries, EXPLAIN, connections, locking | supabase-postgres-best-practices | C:\Users\ingra\.agents\skills\supabase-postgres-best-practices\SKILL.md | C-02, C-04 (EXCLUDE + gist), C-08, C-09, C-10, C-11. Cargar ANTES de tocar DB, aunque sea una columna |
| Designing or reviewing a PostgreSQL-specific schema | postgresql-table-design | C:\Users\ingra\.agents\skills\postgresql-table-design\SKILL.md | C-02 (Rol/Usuario FK simple, Paciente, Profesional, Sillón); C-04 (EXCLUDE anti-solapamiento, TIMESTAMPTZ, NUMERIC); C-08 (FDI 11–48); C-09 (CC derivada); C-10 (recibos sin huecos); C-11 (aranceles por vigencia) |
| Adding caching, distributed lock, rate limiting, pub/sub, key design review | redis-patterns | C:\Users\ingra\.agents\skills\redis-patterns\SKILL.md | C-01 (compose `redis:7`); C-06 (worker + cron 48/24h, idempotencia `turno_id+tipo`, reintentos, mock `WHATSAPP_MOCK=true`); C-07 (oferta 2h + cascada); C-11 (export pesado vía worker) |
| Writing, reviewing, or refactoring React/Next.js code; data fetching, bundle, performance | vercel-react-best-practices | C:\Users\ingra\.agents\skills\vercel-react-best-practices\SKILL.md | Todo frontend C-01 (scaffold Vite+TS), C-03 (auth-context, guards), C-04 (agenda día/semana/mes), C-05 (reserva/confirmar), C-08 (odontograma FDI), C-09/C-10/C-12 (features). Nota: proyecto usa Vite SPA, no Next.js — aplicar reglas de bundle/waterfall/rerender, ignorar RSC/`next/dynamic` |
| Implementing any feature or bugfix, before writing implementation code | test-driven-development | C:\Users\ingra\.agents\skills\test-driven-development\SKILL.md | TODOS los changes (Iron Law RED→GREEN→REFACTOR). Crítico en C-02/C-03/C-04/C-10 (governance CRITICO) |
| Writing Python tests, test suites, TDD, mocking | python-testing-patterns | C:\Users\ingra\.agents\skills\python-testing-patterns\SKILL.md | Backend tests C-01→C-12 (AAA, fixtures, markers, freezegun para tokens 72h / espera 2h, Postgres real — NUNCA SQLite para constraints EXCLUDE) |
| Automate browser interactions, test web pages, Playwright tests | playwright-cli | C:\Users\ingra\.agents\skills\playwright-cli\SKILL.md | C-05 (flujo reserva pública), C-04 (agenda drag), C-12 (E2E demo: landing→reserva→confirmar→agenda→odontograma→presupuesto→cobrar→cierre→liquidación) |
| Building new UI or reshaping an existing one; aesthetic direction, typography | frontend-design | C:\Users\ingra\.config\opencode\skills\frontend-design\SKILL.md | C-01 (shell SPA + design tokens), C-04 (agenda colores por estado), C-05 (reserva/confirmar + landing `/`), C-12 (página `/seguridad`, reseña Google). Mirror: C:\Users\ingra\.agents\skills\frontend-design\SKILL.md |
| Anything with PDF files: read/extract text/tables, merge, split, rotate, watermark, create, forms, encrypt, images, OCR | pdf | C:\Users\ingra\.config\opencode\skills\pdf\SKILL.md | C-11 (`GET /liquidaciones/:id/export.csv\|pdf`, validador cobertura); C-12 (`GET /admin/export-total` vía worker). Mirror: C:\Users\ingra\.agents\skills\pdf\SKILL.md |
| Spreadsheet file is the primary input/output: open/read/edit/fix/create `.xlsx/.xlsm/.csv/.tsv`, convert formats, clean messy tabular data | xlsx | C:\Users\ingra\.config\opencode\skills\xlsx\SKILL.md | C-11 (nomenclador CSV de aranceles) + C-12 (`POST /pacientes/import` Excel/CSV con reporte de errores por fila). Mirror: C:\Users\ingra\.agents\skills\xlsx\SKILL.md |
| Any question about the codebase, its architecture, file relationships, or project content — especially when `graphify-out/` exists (query-first); turns any folder into a navigable knowledge graph (HTML + JSON + GRAPH_REPORT.md) | graphify | C:\Users\ingra\.agents\skills\graphify\skill.md | Transversal (utilidad, no atada a un change): explorar código en cualquier change, documentar arquitectura, auditar. Ya usado: `graphify-out/` con 349 nodos, 396 edges, 47 comunidades. Nota: archivo en minúsculas `skill.md`, no `SKILL.md` |

Nota dedup: `frontend-design`, `pdf`, `xlsx` existen en `~/.config/opencode/skills/` y en `~/.agents/skills/` (mismo contenido, fuente anthropics/skills). Se registra la ruta opencode como canónica; el mirror queda anotado. Las 10 pre-instaladas viven solo en `~/.agents/skills/` (9 originales + graphify).

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### fastapi
- Usar estilo `Annotated[..., Depends(...)]` para params y dependencias; crear alias de tipo reutilizable (`CurrentUserDep = Annotated[...]`)
- NUNCA usar `...` (Ellipsis) como default en path operations ni modelos Pydantic
- Preferir return type (valida/filtra/serializa en Rust); usar `response_model` solo si el schema público difiere del retorno interno
- NO usar `ORJSONResponse`/`UJSONResponse` (deprecados) — el return type ya optimiza
- Declarar `prefix`, `tags`, `dependencies` en el `APIRouter`, no en `include_router()`
- `def` por defecto; `async def` solo si TODO lo llamado adentro es async no bloqueante (vale también para dependencies)
- Una función por operación HTTP; no mezclar GET+POST en la misma función
- No usar Pydantic `RootModel`; usar `Annotated[list[...], Field(...), Body()]`

### fastapi-templates
- Estructura: `app/{api/v1/endpoints,core/{config,security,database},models,schemas,services,repositories}` + `main.py` (en este proyecto: `backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}` según KB `08`)
- Config por env (`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_EXPIRE_MIN, WHATSAPP_*, GCAL_*, CORS_ORIGINS, SEED_ADMIN_*, TZ=America/Argentina/Buenos_Aires`) + `.env.example`; `.env` nunca versionado
- DI con `Depends` para sesión DB, auth (`require_role`), config; sesión async SQLAlchemy 2
- Patrones async de punta a punta (handlers, DB, background tasks, middleware); no bloquear el event loop
- Tests con `httpx.AsyncClient` + `dependency_overrides[get_db]`; ojo: en ESTE proyecto los tests de constraints usan Postgres real (ver python-testing-patterns), no SQLite del ejemplo

### supabase-postgres-best-practices
- Cargar ANTES de cualquier cambio que viva en Postgres, aunque sea una columna o una query
- Prioridad: query performance (missing/partial indexes) → connections (pooling) → security/RLS → schema → locking → access patterns → monitoring → advanced
- Cada regla vive en `references/*.md` (incorrect vs correct SQL + EXPLAIN); leer la regla aplicable antes de escribir DDL/SQL
- RLS: en este proyecto el RBAC es a nivel app (`require_role`); si se evalúa RLS, testear políticas con tests que verifiquen filas visibles por rol
- Ante lentitud/CPU alta/timeouts/locks/bloat: EXPLAIN primero, índice después — nunca adivinar

### postgresql-table-design
- PK `BIGINT GENERATED ALWAYS AS IDENTITY`; `UUID` solo si se necesita opacidad/globalidad. `serial` prohibido
- Normalizar a 3NF; desnormalizar solo con medición que lo justifique
- `NOT NULL` + `DEFAULT` donde aplique; `TIMESTAMPTZ` (nunca `timestamp` solo); `NUMERIC` para dinero; `TEXT` (+`CHECK LENGTH`) para strings; `BOOLEAN NOT NULL`
- Indexar TODA FK manualmente (Postgres no lo hace solo); filtros/sorts/join keys frecuentes; considerar partial/expression/covering/GIN/GiST según caso
- `UNIQUE` permite múltiples NULLs — usar `UNIQUE NULLS NOT DISTINCT` (PG15+) si se quiere un solo NULL
- Anti-solapamiento de este proyecto: `EXCLUDE USING gist (profesional WITH =, tstzrange WITH &&)` ídem sillón; requiere `btree_gist` (C-01 init SQL) — sobreturno solo con `sobre_turno=true + motivo` auditado
- `snake_case` sin comillas; secuencias con gaps son normales; `NUMERIC(2,0)` no trunca: falla con 999
- Enums SQL solo para sets chicos y estables; valores de negocio evolutivos → `TEXT + CHECK` o lookup table; JSONB solo para atributos opcionales (GIN)

### redis-patterns
- Todo key con TTL (sesión 24h, response cache 5–15min, tokens 5–10min); sin TTL = memory pressure
- Cache-aside con `setex`; invalidación por tags (set de keys + `delete`); ante stampede usar lock distribuido (`SET NX PX` + release Lua que verifica token)
- Locks: `acquire_lock` con TTL > duración del job, release en `finally`; multi-nodo → `redlock-py`
- Rate limit: fixed-window con pipeline para bajo tráfico; sliding-window Lua (ZADD/ZREMRANGEBYSCORE) para throttling preciso
- Notificaciones/eventos: Streams + consumer groups (at-least-once, `XACK`, replay) si hay garantías; Pub/Sub solo fire-and-forget
- C-06/C-07: encolado idempotente (`turno_id+tipo`), reintentos con backoff, registrar estado + costo Meta; NUNCA `KEYS *` en prod (usar `SCAN`); blobs >100KB fuera de Redis
- Pool de conexiones dimensionado (`ConnectionPool`, timeouts 2s); política evicción según uso (`allkeys-lru` para cache general)

### vercel-react-best-practices
- Waterfalls: `Promise.all()` para fetches independientes; arrancar promesas temprano, awaitear tarde; `Suspense` para streamear
- Bundle: imports directos (no barrel files); `next/dynamic`-equivalente (lazy) para componentes pesados (odontograma, agenda); analytics/logging después de hydration; preload en hover/focus
- Data fetching cliente: deduplicar (SWR), listeners globales deduplicados y pasivos para scroll, localStorage versionado y mínimo
- Re-renders: no suscribirse a estado solo usado en callbacks; memo solo para trabajo caro; deps primitivas en effects; derivar en render (no en effects); `startTransition`/`useDeferredValue` para lo no urgente; NUNCA definir componentes dentro de componentes
- Adaptación Vite (sin Next.js/RSC en este proyecto): ignorar reglas `server-*`/RSC; aplicar bundle/waterfall/rerender/rendering/js tal cual

### test-driven-development
- Iron Law: NADA de código productivo sin un test en fallo primero; código antes del test → borrar y empezar de cero
- Ciclo RED (un comportamiento, nombre claro, código real sin mocks salvo inevitables) → verificar que FALLA por la razón esperada → GREEN mínimo (YAGNI, sin extras) → verificar que PASA + suite intacta → REFACTOR sin cambiar comportamiento
- Test que pasa de inmediato = testea comportamiento existente → arreglar el test; test que erroréa = arreglar hasta que falle correctamente
- Verificación final con el comando del proyecto (bare `pytest`), no solo el archivo tocado; todo fallo — aunque preexista — se reporta por nombre
- Bug encontrado → primero test que lo reproduce, después fix; refactor/excepciones (prototipo descartable, config) solo con permiso del compañero humano

### python-testing-patterns
- Estructura AAA (Arrange/Act/Assert); tests independientes, sin estado compartido, cada uno limpia lo suyo
- Nombres `test_<unidad>_<escenario>_<resultado>`; organización `tests/{conftest.py,test_unit,test_integration,test_e2e}`
- Parametrizar casos + markers (`slow`, `integration`, `skipif`, `xfail`); cobertura con `pytest-cov` (umbral, ej. `--cov-fail-under=80`), apuntar a cobertura significativa no solo alta
- Mockear dependencias externas con `side_effect` (reintentos, errores permanentes vs transitorios); `freezegun` para tiempo (tokens JWT 30min, reserva 72h, espera 2h)
- Async/concurrencia: testear turnos concurrentes y anti-solapamiento contra Postgres REAL (nunca SQLite — no soporta EXCLUDE/GiST); DB por test con rollback/seed idempotente
- Avanzado en `references/advanced-patterns.md` (async, monkeypatch, property-based, DB testing, CI)

### playwright-cli
- Flujo: `open` → `goto` → `snapshot` → interactuar por refs (`click e15`, `fill e5 "..." --submit`) → `snapshot` → `close`; `find` para buscar en snapshots grandes
- Selectores: preferir refs del snapshot; fallback CSS/role/testid; `eval` para atributos no visibles; `snapshot --depth/--boxes` para eficiencia
- Sesiones nombradas (`-s=name`) + perfil persistente para flujos con login; `state-save/state-load` para reusar auth; `--mobile` para snapshots livianos
- Formularios: `fill` + `click`, manejar diálogos (`dialog-accept/dismiss`); `route` para mockear red; `console`/`requests`/`tracing` para debug
- E2E de este proyecto: `recording-start/stop` para generar código Playwright; adjuntar screenshot/video al PR con `gh pr comment --attach`; URLs con `&` en PowerShell → `playwright-cli --% goto "..."`

### frontend-design
- Diseñar como estudio con identidad propia: paleta/tipo/layout deliberados para ESTE brief (consultorio odontológico AR, 3 roles + paciente); riesgo estético justificado, nada de defaults templated
- Proceso en dos pasadas: plan compacto (color 4–6 hex, tipos y roles, layout con wireframe ASCII, principios) → revisar contra el brief (si suena a genérico, cambiar y decir por qué) → recién ahí codear
- Héroe = lo más característico (no big-number+gradiente por defecto); una familia tipográfica o dos bien distintas; líneas <80 chars; sin acentuar una sola palabra del headline, sin ALL CAPS labels, sin eyebrows innecesarios
- Estructura = información (bordes/números/dividers solo si codifican algo real; `01/02/03` solo para secuencias); motion mínimo: un momento orquestado + motion que responde a acción; decoración que no sirve al brief se corta
- Copy desde el usuario final (verbos activos, sentence case, CTA = lo que pasa: "Guardar cambios"); errores/empties con dirección, sin disculpas vagas; `→` en links, `A · B · C`, `#0B0B0B` como negro, mono para labels = tells a evitar salvo que el brief los pida

### pdf
- Leer/extraer: `pypdf.PdfReader` (merge/split/rotate/metadata/watermark/encrypt) + `pdfplumber` (texto con layout, `extract_tables` → `pandas.DataFrame` → xlsx si hace falta)
- Crear presentable: `reportlab` Platypus (`SimpleDocTemplate` + `Paragraph/Spacer/PageBreak`) o Canvas; CLI merge/split con `qpdf`, texto con `pdftotext -layout`, imágenes con `pdfimages`
- NUNCA unicode sub/superíndices en ReportLab (cajas negras) — usar `<sub>`/`<super>` en `Paragraph`; canvas → ajustar tamaño/posición manual
- Formularios → leer `FORMS.md` (`pdf-lib` o pypdf); escaneados → `pdf2image + pytesseract` OCR; ver `REFERENCE.md` para pypdfium2/JS/troubleshooting
- En este proyecto: liquidación y export-total se generan en worker si son pesados; tablas nomenclador verificadas celda por celda antes de entregar

### xlsx
- Crear/editar con fórmulas: `openpyxl`; bulk in/out: `pandas` (`read_excel`/`to_excel`); vistazo: `markitdown file.xlsx` (sin coordenadas — no planear ediciones desde ahí); leer modelo = dos pasadas `load_workbook` (valores `data_only=True` vs fórmulas por defecto)
- REGLAS de salida: fuente profesional; cero errores según `scripts/recalc.py` (`errors_found` = bloqueante; exit 0 no implica limpio si hay `error_summary`); fórmulas SIEMPRE (`'=SUM(B2:B9)'`, nunca total hardcodeado); spec literal (tabs/headers/fórmula exacta); supuestos y números hardcodeados documentados donde se ven; workbook para rellenar = leyenda + 1 fila ejemplo realista
- Recalcular SIEMPRE que haya fórmulas: `python scripts/recalc.py output.xlsx`; verde = evalúa, no = correcto (verificar 2–3 fórmulas a mano primero); enlaces externos `[1]` se pierden con openpyxl+recalc (`--force` acepta la pérdida)
- Fórmulas que sobreviven: Excel-2007 (`SUMIFS/INDEX/MATCH/IFERROR/SUMPRODUCT`) sin prefijo; 6 post-2007 SOLO con `_xlfn.` (`TEXTJOIN/CONCAT/IFS/SWITCH/MAXIFS/MINIFS`); PROHIBIDO `XLOOKUP/XMATCH/SORT/FILTER/UNIQUE/SEQUENCE` (usar `INDEX/MATCH`, ordenar/dedup en Python)
- openpyxl: `data_only=True` + save = destruye fórmulas; `data_only` recién escrito = `None` (recalcular primero); merged → escribir solo top-left; `.xlsm` con `keep_vba=True`; sheet con espacio → `'Hoja X'!$B$5`; modelos financieros: azul input / negro fórmula / verde link interno / rojo link externo / amarillo a rellenar

### graphify
- Fast path: si existe `graphify-out/graph.json` y el pedido es una pregunta sobre el código (no rebuild) → ir directo a `graphify query "<pregunta>"`, sin re-extraer
- Tres salidas por corrida: `graphify-out/graph.html` (viz navegable), `graph.json` (GraphRAG-ready), `GRAPH_REPORT.md` (resumen en lenguaje claro)
- Audit trail honesto: edges `EXTRACTED` (del texto) vs `INFERRED` (deducidas) vs `AMBIGUOUS` (dudosas) — nunca presentar INFERRED como hecho
- Queries: `query` (BFS contexto amplio / `--dfs` para trazar un path, `--budget N` tope tokens), `path "<A>" "<B>"` (camino más corto entre conceptos), `explain "<nodo>"` (explicación clara)
- Rebuild incremental con `--update` (solo archivos nuevos/cambiados); `--cluster-only` re-hace comunidades sin re-extraer; `--watch` auto-reconstruye al cambiar código
- `/graphify --help` solo imprime el bloque Usage y termina (sin correr nada); sin path usa `.`; URLs GitHub se clonan antes de extraer
- En este proyecto: el grafo ya existe (`graphify-out/`, 349 nodos / 396 edges / 47 comunidades) — las preguntas de arquitectura/exploración en cualquier change se responden contra él primero

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| (ninguno aún) | — | Sin `AGENTS.md`/`CLAUDE.md`/`.cursorrules`/`GEMINI.md`/`copilot-instructions.md` en la raíz — se generan en fase `agents` (posterior). Re-correr `/active-orchestrator:registry` entonces para indexarlas. |
| KB (fuente de verdad, no convenciones de agente) | `knowledge-base/` (11 archivos) + `CHANGES.md` | Los sub-agentes leen los `Leer antes` de cada change; no se duplica contenido acá. |

## Change → Skills (resolución rápida por change)

| Change | Skills principales |
|--------|-------------------|
| C-01 foundation-setup | fastapi, fastapi-templates, vercel-react-best-practices, frontend-design, test-driven-development, python-testing-patterns, redis-patterns, supabase-postgres-best-practices |
| C-02 identidad | postgresql-table-design, supabase-postgres-best-practices, fastapi-templates, test-driven-development, python-testing-patterns |
| C-03 auth-rbac | fastapi, test-driven-development, python-testing-patterns, vercel-react-best-practices |
| C-04 agenda ⭐ | postgresql-table-design (EXCLUDE), supabase-postgres-best-practices, fastapi, vercel-react-best-practices, frontend-design, test-driven-development, python-testing-patterns, playwright-cli |
| C-05 reserva pública | fastapi, vercel-react-best-practices, frontend-design, test-driven-development, python-testing-patterns, playwright-cli |
| C-06 whatsapp | redis-patterns, fastapi, test-driven-development, python-testing-patterns |
| C-07 lista espera | redis-patterns, fastapi, vercel-react-best-practices, test-driven-development, python-testing-patterns |
| C-08 odontograma | postgresql-table-design, fastapi, vercel-react-best-practices, test-driven-development, python-testing-patterns |
| C-09 presupuestos/CC | postgresql-table-design, fastapi, vercel-react-best-practices, test-driven-development, python-testing-patterns |
| C-10 caja (simulada) | postgresql-table-design, fastapi, vercel-react-best-practices, test-driven-development, python-testing-patterns |
| C-11 OS/liquidación | postgresql-table-design, pdf, xlsx, redis-patterns (export pesado), fastapi, test-driven-development, python-testing-patterns |
| C-12 admin/demo | xlsx (import), pdf (export-total), fastapi, vercel-react-best-practices, frontend-design, playwright-cli (E2E), test-driven-development, python-testing-patterns |
| *Transversal (todos los changes)* | graphify (utilidad: explorar código, documentar arquitectura, auditar; query-first contra `graphify-out/` existente; no atada a ningún change) |

## Instalación — graphify (replicar en otra máquina)

> Verificado 2026-10-06 en este equipo (paquete `graphifyy` 0.9.71 instalado vía pip). Dos piezas: el motor Python + el skill file.

```powershell
# 1. Motor Python (elegir UNA vía; el paquete PyPI se llama graphifyy con doble "y", el módulo/binario es graphify)
pip install graphifyy
# o: uv tool install graphifyy

# 2. Verificar binario
Get-Command graphify  # → ...\Python313\Scripts\graphify.exe

# 3. Skill file: copiar la carpeta a los skills del agente
# Origen:  C:\Users\ingra\.agents\skills\graphify\  (archivo skill.md en minúsculas)
# Destino: <tu-home>\.agents\skills\graphify\
# En opencode el skill se resuelve por la ruta registrada en la tabla User Skills ↑
```

Uso en este proyecto: el grafo ya está construido en `graphify-out/` (349 nodos, 396 edges, 47 comunidades; `graph.html` + `graph.json` + `GRAPH_REPORT.md`). Los compañeros que clonen el repo lo heredan — solo necesitan el motor instalado para correr `graphify query "<pregunta>"`; re-extraer con `/graphify <path> --update` solo si cambia el código.
