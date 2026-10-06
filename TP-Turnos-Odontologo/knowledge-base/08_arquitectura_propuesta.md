# Arquitectura Propuesta

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Capas (api / servicios / repos) | Backend FastAPI | Separa HTTP, lógica y persistencia; testeable sin DB |
| Repository sobre SQLAlchemy 2 async | Acceso a datos | Cambia persistencia sin tocar servicios |
| Worker + cola Redis | Recordatorios, notificaciones, exports | No bloquea requests; reintentos |
| Token público un solo uso | Confirmación paciente | Paciente sin cuenta, seguro y simple |
| Soft-delete + contramovimientos | Clínica, cobros | Trazabilidad legal/contable |
 | RBAC por rol | Toda la API | 3 roles + público (ver `03`; Dueño = alias de Admin) |
| Cron liviano | Disparo de recordatorios, cierres | Un scheduler en el worker |

## Estructura de directorios

```
tp-turnos-odontologo/
├── docker-compose.yml            # api + worker + postgres + redis
├── backend/
│   ├── Dockerfile
│   └── app/
│       ├── main.py               # FastAPI, routers, middlewares
│       ├── core/                 # config, seguridad JWT, deps
│       ├── api/                  # routers por recurso (auth, turnos, ...)
│       ├── servicios/            # lógica (agenda, cobros, liquidaciones, notif.)
│       ├── repos/                # SQLAlchemy repositories
│       ├── modelos/              # entidades (ver 04)
│       ├── esquemas/             # Pydantic request/response
│       ├── worker/               # jobs Redis (recordatorios, exports)
│       └── tests/
└── frontend/
    ├── Dockerfile
    └── src/
        ├── features/             # agenda, odontograma, caja, liquidaciones, ...
        ├── shared/               # ui, api-client, auth-context
        └── pages/                # públicas (reservas, confirmar, seguridad)
```

## Seguridad

> **Decisión 2026-10-05**: despliegue v1.0 **local (Docker Compose local)**, sin cloud. Datos 100% ficticios y de prueba. Modelo, arquitectura y roadmap quedan preparados para futura producción real (TLS, secretos por entorno, consentimiento, minimización — RN-GL-03).

- Autenticación: JWT Bearer corto + refresh rotativo httpOnly (RN-AU-01).
- Autorización: RBAC en dependencia FastAPI por endpoint (matriz `03`).
- Validación de input: Pydantic estricto en borde; 409 ante solapamiento concurrente.
- Secrets: solo por variables de entorno / `.env` no versionado.
- Datos salud (si escala): cifrado en tránsito (TLS) y reposo, consentimiento registrado, minimización (RN-GL-03); sin PHI en mensajería (RN-CL-04).
- Pagos v1.0 simulados: sin integración real con MercadoPago ni AFIP (post-TP).
- Anti-solapamiento a nivel DB, no solo aplicación (RN-TU-01).

## Despliegue v1.0

Local con `docker-compose.yml` (api + worker + postgres + redis). Sin cloud ni pipeline productivo en v1.0 (decisión 2026-10-05).

## Variables de entorno

| Variable | Descripción | Ejemplo | Sensible |
|---|---|---|---|
| `DATABASE_URL` | Conexión Postgres async | `postgresql+asyncpg://u:p@db:5432/turnos` | Y |
| `REDIS_URL` | Cola y caché | `redis://redis:6379/0` | N |
| `JWT_SECRET` | Firma de tokens | (aleatorio 32B) | Y |
| `JWT_EXPIRE_MIN` | Vida del access token | `30` | N |
| `WHATSAPP_TOKEN` / `WHATSAPP_PHONE_ID` | Credenciales Meta | — | Y |
| `WHATSAPP_WEBHOOK_SECRET` | Firma webhook | — | Y |
| `GCAL_CLIENT_ID/SECRET` | OAuth Google | — | Y |
| `CORS_ORIGINS` | Orígenes frontend | `http://localhost:5173` | N |
| `SEED_ADMIN_EMAIL/PASSWORD` | Admin inicial | — | Y |
| `TZ` | Zona horaria agenda | `America/Argentina/Buenos_Aires` | N |
