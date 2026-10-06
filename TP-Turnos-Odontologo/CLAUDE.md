# TP-Turnos-Odontólogo — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` + `CHANGES.md` + `.atl/skill-registry.md`. No editar a mano sin re-sincronizar ambos archivos.

---

## Stack Tecnológico

| Capa | Tecnologías | Versión mínima |
|---|---|---|
| Backend | Python + FastAPI | Python 3.12, FastAPI 0.110+ |
| Auth | JWT (Bearer) | — |
| ORM | SQLAlchemy 2 (async) | 2.0+ |
| Base de datos | PostgreSQL | 16 |
| Cola / async | Redis (jobs: recordatorios, notificaciones) | 7 |
| Frontend | React + TypeScript + Vite | React 18, TS 5, Vite 5 |
| Contenedores | Docker + Docker Compose | — |
| Utilidades | Excel/CSV (import/export), PDF (recibos, liquidaciones) | — |

Stack impuesto por la facultad — no negociable para el TP.

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito, alcance v1.0, métricas, plazo 12/10/2026 |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, arquitectura, integraciones, API REST |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC, 3 roles + público (Dueño=Admin) |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Entidades, ERD, migraciones, seed |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Reglas codificadas RN-TU/CL/CO/OS/AU/NO/GL |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | 6 épicas, 16 US (turnos prioritario) |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | 7 flujos E2E |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Capas api/servicios/repos, env vars, seguridad |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | DD-01..DD-06, SU-01..SU-04 |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | 11/11 RESUELTAS 2026-10-05 — sin bloqueos |

> 10_preguntas_abiertas.md sin pendientes: las 2 inconsistencias (IN-01 Dueño=Admin, IN-02 rol FK simple) + 9 preguntas están resueltas. No bloquear el primer change.

---

## Skills Disponibles

Fuente: `.atl/skill-registry.md` (12 skills registradas). No re-escanear — consumir el registry.

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | FastAPI, modelos, auth, agenda, clínica, cobros | `fastapi`, `fastapi-templates`, `postgresql-table-design`, `supabase-postgres-best-practices`, `test-driven-development`, `python-testing-patterns` |
| **Backend Async** | Worker Redis, notificaciones, lista espera, exports | `redis-patterns`, `fastapi`, `test-driven-development`, `python-testing-patterns` |
| **Frontend** | React SPA, agenda, reserva, odontograma, caja | `vercel-react-best-practices`, `frontend-design`, `playwright-cli`, `test-driven-development` |
| **Docs/Exports** | Nomenclador, liquidaciones, import/export | `xlsx`, `pdf`, `redis-patterns` (exports pesados vía worker) |

Cargá la skill correspondiente al contexto ANTES de escribir código.

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo). Esta tabla solo mapea skill→rol.

Detalle Change→Skills: ver `.atl/skill-registry.md` §Change → Skills (C-01→C-12).

---

## Roadmap de Changes

El plan de implementación completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 12 changes en 4 fases, 6 GATES.
- **Camino crítico** (7): `C-01 → C-02 → C-03 → C-04 → C-05 → C-09 → C-10`.
- Variante turnos-pura: `C-01 → C-02 → C-03 → C-04 → C-05 → C-06 → C-07`.
- **Primer change**: `C-01 foundation-setup` (compose api+worker+postgres:16+redis:7, skeletons, env, btree_gist).
- **Prioridad**: Turnos/Agenda (Épica A+B) primero. Recorte si atrasa: C-07 → C-11 (PDF) → C-12 (reseñas), nunca C-04/C-05.
- **Restricciones 2026-10-05**: sede única, rol FK simple, Dueño=Admin, pagos simulados, AFIP post-TP, OS ficticia, deploy local, datos ficticios, espera 2h, plazo 12/10/2026.

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá las dependencias del change y los archivos de "Leer antes".

---

## Reglas Duras (específicas del proyecto)

> Reglas globales ya definidas en `~/.claude/CLAUDE.md` (orquestador, governance, TDD, engram): el proyecto las hereda. Acá viven solo las reglas **específicas de este proyecto** + las universales que el global no cubra.

Reglas derivadas del stack real + decisiones 2026-10-05 (confirmadas en checkpoints previos). Son contrato; romperlas es un defecto. Formato `NUNCA X → hacer Y`:

- NUNCA multi-sede en v1.0 → `Sillon.sede` texto libre, sede única; extensible post-TP.
- NUNCA rol Dueño separado ni tabla `usuario_rol` → `usuario.rol_id` FK simple, 3 roles fijos `admin/odontologo/secretaria`, Dueño=alias de Admin (IN-01/IN-02).
- NUNCA pagos reales ni AFIP en v1.0 → medios `efectivo|transferencia|tarjeta_simulada`, AFIP/MP post-TP.
- NUNCA datos reales → 100% ficticios y de prueba; declararlo en `GET /seguridad`; arquitectura lista para prod (RN-GL-03 al escalar).
- NUNCA solapamiento por profesional/sillón → constraint `EXCLUDE USING gist` en DB (requiere `btree_gist` de C-01); sobreturno solo con `sobre_turno=true + motivo` auditado (RN-TU-01/02, RN-GL-02).
- NUNCA tests de constraints en SQLite → Postgres real (SQLite no soporta EXCLUDE/GiST); `freezegun` para tiempos (token 72h, espera 2h, JWT 30min).
- NUNCA PHI por WhatsApp/SMS plano → solo recordatorios/confirmación sin datos clínicos (RN-CL-04, RN-NO-04); verificar firma webhook Meta (RN-AU-04).
- NUNCA saldo CC editable ni recibo con huecos → saldo derivado, anulación por contramovimiento + motivo; cierre de caja diario obligatorio antes del día siguiente (RN-CO-01..04).
- NUNCA presupuesto sin hallazgo → cada ítem referencia hallazgo FDI 11–48 + catálogo cerrado versionado (RN-CL-01/03).
- NUNCA lista de espera sin expiración → oferta al primero compatible, ventana 2h, cascada, si nadie acepta hueco libre (RN-TU-06).
- NUNCA secreto en código → solo env (`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_EXPIRE_MIN=30, WHATSAPP_*, GCAL_*, CORS_ORIGINS, SEED_ADMIN_*, TZ=America/Argentina/Buenos_Aires`); `.env.example` versionado, `.env` no.
- NUNCA schema Pydantic permisivo → `extra='forbid'`; `Annotated[..., Depends(...)]` para auth/DB; `async def` solo si todo adentro es async no bloqueante.
- NUNCA `any` en TS → tipado estricto, componentes PascalCase, `snake_case` + type hints en Python.
- NUNCA lógica fuera de capas → `backend/app/{api,servicios,repos,modelos,esquemas,worker,tests}`, `frontend/src/{features,shared,pages}` según `08`; soft-delete clínico/administrativo (RN-GL-01).
- NUNCA buildear/commitear/pushear sin pedido explícito → proponer y esperar; commits convencionales sin co-autoría IA.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias y GATES
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks (cargando skills)       → respetando las reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen. Change→Skills se resuelve desde `.atl/skill-registry.md`.
