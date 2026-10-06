# Resumen de sesión — 2026-10-06

## Objetivo
Retomar el TP-Turnos-Odontólogo, completar la fundación del proyecto (KB → roadmap → skills → agents) y avanzar el primer change C-01 hasta archivarlo.

## Instrucciones / preferencias del usuario
- Stack impuesto por la facultad: Python + FastAPI + JWT + SQLAlchemy + PostgreSQL + Redis + Docker/Compose; React + TS + Vite. Equipo de 3.
- Decisiones KB-10 (2026-10-05/06): Dueño = Admin (alias), rol simple por FK, sin consultorio piloto (datos 100% ficticios pero arquitectura lista para producción), OS ficticia, turnos pondera la evaluación, AFIP en escalamiento, pagos simulados, deploy local, plazo 12/10/2026, sede única, lista de espera 2h.
- El usuario sube a GitHub por su cuenta (respaldos manuales). NO hacer commit/push sin pedido explícito.
- El usuario no tiene Docker local todavía; lo instala mañana.
- Revisión C-01 (5 preguntas): todo OK como propuesto (carpetas en español, sin Alembic en C-01, worker reusa imagen api, WHATSAPP_MOCK=true, 3 placeholders).

## Descubrimientos
- `openspec` CLI bloqueado por ExecutionPolicy en PowerShell 5.1 → usar `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force` antes.
- `npx` también afectado por lo mismo; `npx skills add -g` instala en `~\.agents\skills`, NO en opencode global → hay que espejar con `Copy-Item` a `~\.config\opencode\skills`.
- El CLI de openspec exige nombres de change en minúsculas (`c-01-foundation-setup`).
- Sin Docker ni repo git en este entorno: 2 tests E2E skipean con mensaje accionable.
- Engram NO disponible en esta sesión (sin tools MCP ni CLI) → la persistencia fue vía archivos del repo.
- Skills oficiales: `frontend-design` (Apache 2.0), `pdf` y `xlsx` (© 2025 Anthropic), fuente `anthropics/skills`.

## Logrado
- ✅ Fundación completa (`step=done`): `discovery/` + `knowledge-base/` (11 archivos, 11/11 preguntas RESUELTAS) + `CHANGES.md` (12 changes, 6 gates) + 12 skills instaladas y registradas en `.atl/skill-registry.md` + `AGENTS.md`/`CLAUDE.md` (15 reglas duras) + `openspec/config.yaml` con contexto.
- ✅ C-01 `foundation-setup` propuesto → aplicado (30 passed + 2 skipped, tsc y vitest verdes, 34 archivos) → archivado en `openspec/changes/archive/2026-10-05-c-01-foundation-setup/` con G5.1 pendiente explícita. Specs sincronizados en `openspec/specs/foundation-setup/` (6 requirements, validate OK).
- ✅ Bloque de comandos para compañeros (instalar las 3 skills) entregado.
- ✅ Pipeline `/graphify` corrido: 349 nodos, 396 edges, 47 comunidades; salidas en `graphify-out/` (graph.html, GRAPH_REPORT.md, graph.json, cost.json, manifest.json).

## Próximos pasos
1. Usuario: instalar Docker Desktop (o que un compañero corra el E2E).
2. Cerrar G5.1: `docker compose up -d --build` + `pytest backend/app/tests -v` (esperado 32 passed, 1 skipped) → marcar `- [x] 5.1` en el tasks.md archivado.
3. Subir a GitHub los 34 archivos de C-01 + archive (lo hace el usuario).
4. Seguir con `/opsx:propose C-02 core-models-identidad-pacientes` (GATE 0 liberado).
5. Verificar si Engram está disponible en el setup para persistencia entre sesiones.

## Archivos relevantes
- `CHANGES.md` — roadmap (C-01 [x], resto pendiente)
- `.active-orchestrator-state.json` — step=done
- `.atl/skill-registry.md` — 12 skills + Change→Skills
- `openspec/specs/foundation-setup/spec.md` — 6 requirements
- `openspec/changes/archive/2026-10-05-c-01-foundation-setup/tasks.md` — 15/16, G5.1 pendiente
- `docker-compose.yml`, `.env.example`, `backend/`, `frontend/` — código C-01
- `graphify-out/` — grafo de conocimiento del proyecto
