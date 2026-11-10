# Turnos Odontólogo

Sistema web de gestión para consultorios odontológicos desarrollado bajo **Spec-Driven Development (SDD / OpenSpec)** y la fundación **Active Stack**. Cubre el circuito completo **turno → clínica → cobro**:

- **Agenda y turnos**: agenda multi-profesional con estados de turno (`pendiente`, `confirmado`, `asistido`, `ausente`, `cancelado`), sin solapamiento por profesional o sillón garantizado a nivel base de datos (`EXCLUDE USING gist` + `btree_gist`), sobreturnos auditados, reserva online pública con token de un solo uso (expiración 72 h), recordatorios por WhatsApp (modo mock por defecto, sin PHI) y lista de espera con ofertas en cascada que vencen a las 2 h.
- **Clínica**: odontograma digital interactivo con notación FDI (piezas 11–48), historia clínica con alertas visibles de alergias/antecedentes, catálogo cerrado de hallazgos y tratamientos, y presupuestos armados trazablemente desde los hallazgos del odontograma.
- **Cobros**: cuenta corriente por paciente con saldo derivado inmutable (anulación únicamente por contramovimiento con motivo), caja diaria con cierre obligatorio antes de operar al día siguiente y recibos secuenciales sin huecos (medios simulados: `efectivo`, `transferencia`, `tarjeta_simulada`).
- **Obras sociales**: validación de cobertura, gestión de planes y aranceles por vigencia histórica, y liquidación mensual por nomenclador con exportación a CSV y PDF.
- **Administración y Experiencia Visual**: tres roles (`admin`, `odontologo`, `secretaria` + acceso público), resguardo del último administrador activo, auditoría administrativa, importación masiva de pacientes desde Excel/CSV con reporte de errores por fila, exportación total anti-lock-in, página pública `/seguridad`, diseño visual cohesivo con tokens CSS y modo claro/oscuro alternable.

> **Trabajo Práctico Integrador — Metodología de Sistemas I (UTN - TUP).**  
> **Todos los datos son 100 % ficticios**: no cargar datos reales de pacientes ni credenciales verdaderas. Los pagos y envíos de WhatsApp son simulados en entorno local.

---

## Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI 0.110+, SQLAlchemy 2 (async), Alembic, Pydantic v2 (`extra='forbid'`), JWT (Bearer + Argon2) |
| Base de datos | PostgreSQL 16 (`btree_gist` para restricciones de exclusión temporal) |
| Cola de trabajos | Redis 7 (worker asíncrono para recordatorios, ofertas de lista de espera y exportaciones) |
| Frontend | React 18 + TypeScript 5 + Vite 5 + CSS modular tokenizado (`tokens.css`) |
| Testing | Pytest + `httpx` + `freezegun` (Backend contra Postgres/Redis reales) · Vitest + Testing Library + Playwright MCP (Frontend) |
| Infraestructura | Docker + Docker Compose (local y `compose.prod.yml` opcional para VPS con Easypanel) |

---

## Estructura del Repositorio

```text
backend/          API FastAPI y worker Redis (app/api, servicios, repos, modelos, esquemas, worker, tests)
frontend/         SPA React + TypeScript (src/features, shared, pages, styles)
design-system/    Fundación visual aprobada: tokens.css (claro/oscuro), brand.md y components.html
discovery/        Investigación inicial del dominio odontológico
knowledge-base/   Fuente de verdad del dominio (10 documentos canónicos: visión, roles, ERD, reglas RN-*, flujos)
openspec/         Especificaciones consolidadas (openspec/specs/) y 15 changes archivados (openspec/changes/archive/)
.agents/skills/   Skills del proyecto (incluye la skill propia dental-ui-polish)
.claude/skills/   Skill propia de verificación reproducible en Docker (tp-verify-docker)
.atl/             Registro de skills y reglas compactas por agente (skill-registry.md)
docs/             Runbook de despliegue opcional en VPS (deploy-vps.md)
```

---

## Levantarlo en local

### Requisitos

- **Docker Desktop** (con Docker Compose v2)
- **Node.js 18+** y `npm` (para correr el frontend en modo desarrollo y ejecutar Vitest)
- **Python 3.12+** (opcional si corrés `pytest` desde el host contra los contenedores `db` y `redis`)

### 1. Configurar el entorno (sin secretos reales)

Copiá el archivo de ejemplo versionado `.env.example` a `.env` y ajustá los valores si hace falta:

```sh
cp .env.example .env
```

En PowerShell:

```powershell
Copy-Item .env.example .env
```

Las variables principales en `.env.example` ya vienen listas para desarrollo local con valores de prueba:
- `JWT_SECRET`: cadena aleatoria de al menos 32 caracteres para firmar tokens.
- `SEED_ADMIN_EMAIL` y `SEED_ADMIN_PASSWORD`: credenciales del usuario administrador inicial que crea el seed.
- `WHATSAPP_MOCK=true`: mantiene las notificaciones en modo simulado sin requerir credenciales de Meta.
- El archivo `.env` está excluido en `.gitignore` y **nunca se versiona**.

### 2. Levantar el backend e infraestructura

Con Docker Desktop en marcha:

```sh
docker compose up -d --build
```

Esto levanta cuatro servicios: `db` (PostgreSQL 16 con la extensión `btree_gist`), `redis` (Redis 7), `api` (FastAPI en puerto `8000`) y `worker` (procesador de colas y recordatorios).

> **Nota si ya tenés un PostgreSQL local ocupando el puerto 5432**: podés parametrizar el puerto del contenedor sin modificar `docker-compose.yml`:
> ```sh
> POSTGRES_PORT=5433 docker compose up -d --build
> ```
> En PowerShell:
> ```powershell
> $env:POSTGRES_PORT=5433; docker compose up -d --build
> ```

### 3. Ejecutar migraciones y cargar datos ficticios de prueba (Seed)

Con los contenedores arriba, aplicá las migraciones de Alembic (hasta el head `009_auditoria_admin`) y ejecutá el seed idempotente:

```sh
docker compose exec api alembic upgrade head
docker compose exec api python -m app.db.seed
```

El script `app.db.seed` se puede correr múltiples veces sin duplicar registros. Crea datos **100 % ficticios**:
- Los 3 roles fijos (`admin`, `odontologo`, `secretaria`).
- 1 usuario por rol:
  - **Admin**: el email y contraseña configurados en `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` en tu `.env`.
  - **Odontólogo demo**: `odontologo.demo@example.com`
  - **Secretaría demo**: `secretaria.demo@example.com`
- Sillón demo (`Sillón Demo 1`), profesional demo (`DEMO-0001`) con agenda semanal configurada, catálogo de tratamientos (`CON-001`, `PRO-001`, `OBT-001`, `END-001`, `COR-001`, `EXT-001`), obra social `"OS Ficticia Demo"` con planes/aranceles y pacientes ficticios con turnos, historia clínica, presupuestos y movimientos de muestra.

### 4. Levantar el frontend

```sh
cd frontend
npm install
npm run dev
```

### 5. Accesos al sistema

| Servicio | URL | Descripción |
|---|---|---|
| **Aplicación Web (Frontend)** | http://localhost:5173 | Portal público de reserva/confirmación + panel de gestión por rol |
| **API Backend** | http://localhost:8000 | Endpoints REST + healthcheck en `GET /health` y `GET /seguridad` |
| **Swagger UI (OpenAPI)** | http://localhost:8000/docs | Documentación interactiva para probar endpoints y autenticación Bearer |

### 6. Apagar el entorno

```sh
docker compose down
```

Los datos persisten en los volúmenes `pgdata` y `redisdata`. Usá `docker compose down -v` únicamente si querés borrar los volúmenes y reiniciar la base de datos desde cero.

---

## Ejecución de Tests

### Backend (Pytest contra PostgreSQL 16 y Redis 7 reales)

Las pruebas de backend verifican restricciones `EXCLUDE USING gist`, triggers de inmutabilidad, concurrencia y expiraciones con `freezegun` (no se utiliza SQLite):

```sh
cd backend
pytest
```

> Si levantaste el contenedor `db` en el puerto `5433`, exportá antes la variable de entorno de test:
> ```powershell
> $env:DATABASE_URL_TEST="postgresql+asyncpg://turnos:turnos@localhost:5433/turnos"
> pytest
> ```

### Frontend (TypeScript + Vitest + Build)

```sh
cd frontend
npx tsc --noEmit   # Verificación estricta de tipos (cero any)
npm test           # Suite de 433 tests unitarios y de componentes con Vitest
npm run build      # Compilación de producción con Vite
```

---

## Alcance Alcanzado y Estado del Roadmap (SDD / OpenSpec)

El desarrollo siguió el ciclo completo de **Spec-Driven Development** (`propose → apply → verify → archive`). Todos los artefactos (`proposal.md`, `design.md`, `tasks.md`, `specs/` y capturas en `verify/`) se conservan en [`openspec/changes/archive/`](openspec/changes/archive/) y el detalle operativo figura en [`CHANGES.md`](CHANGES.md).

### Changes Completos, Verificados y Archivados (15 / 15)

| Change | Nombre | Propósito y resultado verificado | Estado |
|---|---|---|---|
| **C-01** | `foundation-setup` | Estructura en capas, `docker-compose.yml` (`api`, `worker`, `postgres:16`, `redis:7`), `.env.example`, extensión `btree_gist` y `/health`. | ✅ Archivado |
| **C-02** | `core-models-identidad-pacientes` | Modelos `Rol`, `Usuario` (FK simple), `Paciente` (soft-delete), `Profesional`, `Sillon`, migración `001` y seed idempotente. | ✅ Archivado |
| **C-03** | `auth-rbac` | Autenticación JWT Bearer + refresh rotativo, hash Argon2, `require_role`, protección de último admin activo y login UI. | ✅ Archivado |
| **C-04** | `agenda-turnos-core` | Modelo `Turno`, constraint `EXCLUDE USING gist` anti-solapamiento, sobreturnos auditados, disponibilidad y vistas día/semana/mes. | ✅ Archivado |
| **C-05** | `reserva-online-publica` | Flujo público sin cuenta: consulta de disponibilidad, reserva con token hash de 1 uso (72 h) y confirmación automática. | ✅ Archivado |
| **C-06** | `notificaciones-whatsapp` | Worker Redis y barrido horario 48/24 h con idempotencia doble, webhook con validación de firma HMAC, modo mock y cero PHI. | ✅ Archivado |
| **C-07** | `lista-espera-cierre-loop` | Cola de espera, oferta automática al liberarse un hueco con ventana de 2 h, cascada al siguiente compatible y conversión a turno. | ✅ Archivado |
| **C-08** | `clinica-odontograma-hc` | Historia clínica con alergias visibles, odontograma FDI (11–48), catálogo cerrado de hallazgos/tratamientos e historial por pieza. | ✅ Archivado |
| **C-09** | `presupuestos-cuenta-corriente` | Presupuestos vinculados a hallazgos del odontograma, paso a cargo automático en cuenta corriente y saldo derivado inmutable. | ✅ Archivado |
| **C-10** | `caja-cobros-simulados` | Cobros simulados, emisión de recibos secuenciales sin huecos, anulación por contramovimiento y cierre diario obligatorio de caja. | ✅ Archivado |
| **C-11** | `obras-sociales-liquidacion` | Obra social ficticia, planes, aranceles por vigencia, validador de cobertura y liquidaciones mensuales exportables a CSV y PDF. | ✅ Archivado |
| **C-12** | `admin-cierre-demo` | ABM de usuarios y aranceles auditado, importación Excel/CSV con errores por fila, exportación total, página `/seguridad` y flujo E2E. | ✅ Archivado |
| **C-13** | `ui-cohesive-design-polish` | Unificación visual de las 12 vistas con `AppHeader`, `tokens.css`, microinteracciones táctiles y accesibilidad WCAG AA. | ✅ Archivado |
| **C-14** | `dark-mode-toggle` | Tema oscuro (`[data-theme="dark"]` en `tokens.css`), detección de `prefers-color-scheme`, persistencia en `localStorage` y toggle en header. | ✅ Archivado |
| **C-15** | `vps-deploy` | Configuración opcional de producción (`compose.prod.yml`, `Dockerfile.prod` con nginx non-root y runbook `docs/deploy-vps.md`). | ✅ Archivado |

### Qué queda pendiente o fuera del alcance v1.0

1. **Ítems secundarios diferidos en `C-12`**:
   - **R1 — Envío automático de link de reseña de Google post-turno**: la plantilla existe en el seed de notificaciones, pero el disparo automático tras marcar `asistido` quedó diferido por priorización del camino crítico.
   - **R2 — Sincronización en vivo con Google Calendar API**: se mantiene como stub configurable por variables `GCAL_*` sin credenciales reales.
2. **Primer despliegue en servidor VPS externo (`C-15`)**: los artefactos de despliegue (`compose.prod.yml`, `Dockerfile.prod`, `nginx.conf` y `docs/deploy-vps.md`) están completos y verificados en local; la puesta en línea en un VPS real con Easypanel es opcional.
3. **Exclusiones explícitas de v1.0 (definidas en la Knowledge Base para etapas post-TP)**: cobros reales con Mercado Pago, facturación electrónica AFIP, multi-sede física, imágenes radiográficas/periodontograma y portal con cuenta para pacientes.

---

## Skills Propias y Servidor MCP Integrados

Como parte de la integración de **MCP + Skills** del Trabajo Práctico Integrador, el proyecto incorpora **dos skills propias** versionadas en el repositorio y la conexión del servidor **Playwright MCP**.

### 1. Skill propia de Diseño e Interfaz: `dental-ui-polish`

- **Ubicación en el repositorio**: [`.agents/skills/dental-ui-polish/SKILL.md`](.agents/skills/dental-ui-polish/SKILL.md) (referenciada en [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) y [`.atl/skill-registry.md`](.atl/skill-registry.md)).
- **Qué necesidad resuelve**: Durante los primeros 12 changes (`C-01` a `C-12`), el frontend se construyó priorizando los contratos REST y las reglas de negocio con HTML semántico plano. Hacía falta unificar las 12 pantallas (públicas de paciente y operativas del personal) bajo la identidad aprobada en `design-system/tokens.css`, sin introducir librerías CSS pesadas ni romper ninguno de los **421 tests existentes en Vitest**.
- **Cómo se creó y adaptó**: Se diseñó tomando como referencia las skills `frontend-design` y `emil-design-eng` junto con la fundación local `design-system/`. Se adaptó específicamente al dominio odontológico argentino definiendo:
  1. Uso exclusivo de variables semánticas de `tokens.css` (`--color-primary`, `--estado-pendiente`, `--estado-confirmado`, etc.), prohibiendo colores hexadecimales hardcodeados.
  2. Clases estructurales estándar (`.wrap`, `.topbar`, `.btn`, `.card`, `.field`, `.table-wrap`).
  3. Microinteracciones táctiles (`:active scale(0.97)`, transiciones de `120ms ease-out`, respeto por `prefers-reduced-motion`) y contraste accesible WCAG AA.
  4. Diferenciación de densidad visual: vistas públicas móviles (390×844, objetivos táctiles ≥ 44 px, voseo rioplatense) vs. vistas de staff de escritorio (1440×900, alta densidad tabular).
  5. **Regla dura de invarianza de tests**: prohibición de alterar `data-testid`, roles ARIA, `id`/`htmlFor` o firmas de props evaluadas por Vitest.
- **Aplicación concreta**: Se aplicó en **[C-13 `ui-cohesive-design-polish`](openspec/changes/archive/2026-11-03-c-13-ui-cohesive-design-polish/proposal.md)** para crear el shell `AppHeader` y estilizar las 12 vistas del sistema, y en **[C-14 `dark-mode-toggle`](openspec/changes/archive/2026-11-03-c-14-dark-mode-toggle/proposal.md)** para extender los tokens al modo oscuro (`[data-theme="dark"]`) pasando de 421 a **433 tests en verde** sin regresiones.

### 2. Skill propia de Verificación E2E: `tp-verify-docker`

- **Ubicación en el repositorio**: [`.claude/skills/tp-verify-docker/SKILL.md`](.claude/skills/tp-verify-docker/SKILL.md) y su configuración de proyecto [`.claude/skills/tp-verify-docker/references/tp-turnos-config.md`](.claude/skills/tp-verify-docker/references/tp-turnos-config.md).
- **Qué necesidad resuelve**: Estandariza la fase de verificación (`verify`) previa a archivar cualquier change en OpenSpec, evitando falsos positivos (como correr tests de exclusión GiST en SQLite o dejar contenedores huérfanos).
- **Cómo funciona y dónde se aplicó**: Define el protocolo reproducible de 8 pasos (pre-flight de secretos, resolución de conflicto de puerto `5432 → 5433`, levantado de `db + redis`, migración limpia desde cero con `alembic upgrade head`, corrida completa de Pytest + Vitest + `tsc --noEmit` + `vite build`, auditoría estática de reglas duras, reporte estructurado VERDE/ROJO y apagado limpio con `docker compose down`). Se utilizó para verificar y certificar los cierres de los changes hasta `C-15`.

### 3. Servidor MCP Conectado: `Playwright MCP` (`@playwright/mcp`)

- **Qué servidor se conectó y qué capacidades aporta**: Se integró el servidor **Playwright MCP** local (sin costos, sin cuentas en la nube ni credenciales externas). Aporta herramientas reales de automatización e inspección de navegador para el agente: navegación (`browser_navigate`), redimensionado de viewport (`browser_resize`), inspección del árbol de accesibilidad (`browser_snapshot`), interacción con formularios y botones (`browser_click`, `browser_fill_form`, `browser_select_option`) y captura de evidencia visual (`browser_take_screenshot`).
- **Instrucciones reproducibles de conexión (sin credenciales)**:
  Para conectar el servidor MCP en cualquier cliente compatible (Claude Code, Antigravity, Cursor u OpenCode), agregá la siguiente entrada en la configuración de servidores MCP del agente:
  ```json
  {
    "mcpServers": {
      "playwright": {
        "command": "npx",
        "args": ["@playwright/mcp@latest"]
      }
    }
  }
  ```
- **Cómo se comprobó la conexión y en qué changes se aplicó**:
  1. **Fundación del Sistema de Diseño (`design-system/`)**: Se utilizó `browser_navigate`, `browser_resize` y `browser_take_screenshot` sobre `design-system/components.html` en viewports móvil (`390×844`) y escritorio (`1440×900`), generando las capturas [`design-system/previews/components-mobile.png`](design-system/previews/components-mobile.png) y [`design-system/previews/components-desktop.png`](design-system/previews/components-desktop.png).
  2. **Verificación de flujos y pantallas en `C-09`, `C-10`, `C-12`, `C-13` y `C-15`**: Con el frontend (`localhost:5173`) y el backend (`localhost:8000`) en ejecución, se ejecutaron las herramientas del MCP para recorrer el circuito real (reserva pública, confirmación, login, agenda, odontograma, presupuesto, cobro en caja, liquidación de obra social, página de seguridad y administración de usuarios) y auditar la respuesta visual en móvil y escritorio.
  3. **Evidencia versionada en el repositorio**: Las capturas obtenidas mediante el MCP se encuentran archivadas junto a sus respectivos changes en:
     - [`openspec/changes/archive/2026-10-30-c-09-presupuestos-cuenta-corriente/verify/`](openspec/changes/archive/2026-10-30-c-09-presupuestos-cuenta-corriente/verify/) (9 capturas)
     - [`openspec/changes/archive/2026-10-31-c-10-caja-cobros-simulados/verify/`](openspec/changes/archive/2026-10-31-c-10-caja-cobros-simulados/verify/) (17 capturas)
     - [`openspec/changes/archive/2026-11-02-c-12-admin-cierre-demo/verify/`](openspec/changes/archive/2026-11-02-c-12-admin-cierre-demo/verify/) (20 capturas del flujo E2E completo)
     - [`openspec/changes/archive/2026-11-06-c-15-vps-deploy/verify/`](openspec/changes/archive/2026-11-06-c-15-vps-deploy/verify/) (`root.png`, `agenda.png`, `lista-espera.png`)

---

## Producción (Opcional)

El repositorio incluye un despliegue opcional para VPS con Easypanel / Traefik en [`compose.prod.yml`](compose.prod.yml) y [`frontend/Dockerfile.prod`](frontend/Dockerfile.prod), manteniendo intacto `docker-compose.yml` para desarrollo y verificación local. El paso a paso completo está documentado en [`docs/deploy-vps.md`](docs/deploy-vps.md).

## Documentación Adicional

- [`knowledge-base/`](knowledge-base/01_vision_y_objetivos.md): Visión, actores y roles, modelo de datos (ERD), reglas de negocio (`RN-*`), funcionalidades, flujos E2E y arquitectura.
- [`CHANGES.md`](CHANGES.md): Roadmap completo de implementación, árbol de dependencias, gates y trazabilidad de los 15 changes (`C-01` a `C-15`).
- [`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md): Instrucciones operativas para agentes, gobernanza por dominio y reglas duras del proyecto.
