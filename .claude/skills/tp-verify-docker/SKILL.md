---
name: tp-verify-docker
description: Reproducible verify flow for Docker Compose projects (Postgres + Redis + FastAPI + Vite React). Use whenever the user says verifica, verify, corre el verify, valida el change, prende docker y proba todo, check pre-archive, or asks to validate a change before archiving — even if they don't say the word verify explicitly. Runs pre-flight, Docker start, port resolution, migrations, backend + frontend tests, openspec validate, failure classification, hard-rule checks, VERDE/ROJO report, and safe shutdown.
---

# TP Verify Docker

Reproducible end-to-end verification for Docker Compose projects. General core workflow plus a project-specific config overlay (see `references/`).

## When to load the config overlay

SKILL.md is generic. Project specifics (ports, compose services, migration heads, env names) live in `references/`. Before running, check if a config file matches the current repo:

- If repo is TP-Turnos-Odontologo (FastAPI + Postgres 16 + Redis 7 + React/Vite) → read `references/tp-turnos-config.md` and let its values override the defaults below.
- If no config matches → use the defaults inline and ask the user for the 4 values: compose file path, DB port, test DB URL env name, frontend test command.

Why this split exists: ports, seed credentials and flaky-test lists change per project, but the verify sequence does not. Keeping them separate lets the core stay reusable.

## Preconditions (ask before touching Docker)

1. Ask the user for explicit permission to start Docker Desktop and run containers. Explain that verify implies: starting Docker Desktop, lifting `db+redis` (+ api/worker if compose defines them), running migrations, seeds and the full test suite.
2. Confirm the mode: `quick`, `full`, or `demo-e2e` (definitions below). Default to `quick` unless the user says archive or pre-archive (then use `full`).
3. Check Docker Desktop is running. If not, start it from its install location (on Windows typically per-user `AppData\Local\Programs\DockerDesktop`; on other OS use `open -a Docker` / `systemctl`). Wait for the daemon (`docker info` succeeds) before continuing — otherwise every later step fails confusingly.

## Modes

- **quick**: targeted backend tests for the change (`pytest -k <change-keyword>`) + frontend typecheck (`tsc --noEmit`). Fast gate before archive review.
- **full**: clean migration from scratch + seed, full backend suite, frontend `vitest run` + `tsc --noEmit` + `vite build`, `openspec validate --all --strict`. Required before `/opsx:archive`.
- **demo-e2e**: Playwright critical path only (booking flow). Run only when the change explicitly touches E2E/demo (e.g. C-12 in TP-Turnos). Needs browsers installed.

Pick the mode first because it determines how long Docker stays up and what counts as VERDE.

## Verify sequence

Follow in order. Stop and report ROJO at the first blocking failure, but still run the shutdown step.

### 1. Pre-flight checks

- `docker info` works (daemon up).
- Compose file exists; required env file / `.env.example` present; `.env` is gitignored and never committed.
- No secret is hardcoded: grep for `JWT_SECRET`, `DATABASE_URL`, passwords in tracked files. Secrets come only from env — this is why leaks are caught here instead of in production.
- Required DB extension present in config (e.g. `btree_gist` for exclusion constraints in TP-Turnos). If the extension is missing, overlap constraints silently don't exist.

### 2. Resolve port conflicts

- Check whether the default Postgres port is occupied (on dev machines a local PG18 often holds 5432).
- If occupied, override with an env var (e.g. `POSTGRES_PORT=5433`) and set the test DB URL accordingly (e.g. `DATABASE_URL_TEST=postgresql+asyncpg://...@localhost:5433/...`). Never edit the committed compose file for a local conflict — env override keeps the repo clean.
- Do the same for Redis if needed.

### 3. Start services and migrate clean

- Step 0: resolver `<change>` con `openspec list` (via `cmd /c` on Windows); si no existe → ROJO inmediato indicando changes disponibles — no adivinar nombres ni validar el change equivocado.
- `docker compose up -d db redis` (add `api worker` only if the verify needs a live API).
- Run migrations from scratch on the test DB (`alembic upgrade head`). A clean-from-zero run catches missing heads and broken downgrade chains that incremental runs hide.
- Verify expected heads exist (TP-Turnos: `001`, `002`, `003` — read the overlay for the current list). If `alembic history` shows a different head, report it; a downgrade test assuming an old head is a known false ROJO.
- Run seed only if the project defines one (idempotent seed; test data must be 100% fictitious).

### 4. Run tests per mode

- **Backend**: `pytest` (quick: `-k <keyword>`; full: whole suite). Known flakiness to expect, not to hide: concurrent overlap tests can flake under load — retry up to x3 before declaring ROJO, and say so in the report. Time-sensitive tests need frozen time (`freezegun`) plus Pydantic `TypeAdapter` warmup, otherwise JWT/token windows (30 min / 72 h / 2 h) produce flaky reds.
- **Frontend**: `tsc --noEmit` always; full adds `vitest run` and `vite build`.
- **Spec**: `openspec validate` (full: `--all --strict`).
- Record counts as `passed/total` per layer. Never run constraint tests against SQLite — exclusion/GiST constraints only exist in real Postgres, so SQLite gives false greens. Si `pytest -k <keyword>` colecta 0 tests → ROJO con `Nuevos fallos: sin cobertura para <keyword>`; nunca VERDE con `0/0` — cero tests colectados es falta de cobertura, no éxito.

### 5. Classify failures (new vs pre-existing)

- For every failure, decide: **new** (introduced by this change) or **pre-existing** (fails on the base commit too). When in doubt, stash the change and rerun the single failing test on base.
- Pre-existing failures do not block VERDE by themselves, but they must be listed explicitly so archive doesn't launder them as fixed.

### 6. Hard-rule checks (project overlay defines the list)

Run the static checks; any violation is ROJO even if tests are green, because tests don't cover conventions:

- Pydantic schemas use `extra='forbid'`.
- Auth/DB dependencies use `Annotated[..., Depends(...)]`.
- No `any` in TypeScript (strict typing).
- Soft-delete where the domain requires it (TP-Turnos RN-GL-01: clinical/administrative data).
- Derived balances / no editable computed fields (TP-Turnos RN-CO: caja saldo derivado, anulación por contramovimiento).
- No clinical data (PHI) in notification payloads.

### 7. Report (ALWAYS use this template)

```markdown
## Verify <change> — <modo> — <VERDE|ROJO>
- Backend: <passed>/<total>
- Frontend: <vitest passed>/<total> + tsc <OK|FAIL> (+ build <OK|FAIL> si full)
- Validate: <passed>/<total>
- Migración limpia: <SI|NO> (heads: <lista>)
- Docker apagado: <SI|NO>
- Nuevos fallos: <lista o "ninguno">
- Pre-existentes: <lista o "ninguno">
- Veredicto: <VERDE → se puede archivar | ROJO → fix <archivos> y re-verify>
- Next action: <archive <change> | fix + re-verify modo <quick|full>>
```

Report counts even on ROJO — a report without numbers can't be compared across runs.

### 8. Safe shutdown (never skip)

- `docker compose down` WITHOUT `-v` (volumes stay intact; `-v` deletes test data other changes rely on).
- Close Docker Desktop and confirm the daemon is down (`docker info` fails). Leaving the daemon up wastes resources and holds ports for the next session.
- Mention shutdown status in the report (`Docker apagado: SI/NO`).

## Gotchas worth remembering

- Docker Desktop per-user install path on Windows means system-wide shortcuts may not exist — launch the exe directly.
- Concurrent DB tests + cold Pydantic validation = flaky first run; warmup + retry x3 before blaming the change.
- Downgrade tests hardcode the expected head; update them when a new migration lands instead of forcing the DB backwards.
- `.env` must never be committed; `.env.example` is versioned and is what verify checks against.

## What NOT to do

- Don't start Docker without explicit user permission.
- Don't use `-v` on shutdown, don't edit compose ports permanently for a local conflict, don't run constraint tests on SQLite.
- Don't build, commit or push unless the user explicitly asks — verify proposes, the user disposes.
