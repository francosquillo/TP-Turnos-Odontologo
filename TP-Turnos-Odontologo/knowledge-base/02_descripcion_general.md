# Descripción General

## Stack tecnológico

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

> **Decisión 2026-10-05**: datos 100% ficticios y de prueba obligatorio para el TP (sin consultorio piloto real). Modelo, arquitectura y roadmap quedan preparados para futura producción real.

## Arquitectura general

Monolito modular backend (FastAPI) + SPA (React):

```
                ┌─────────────┐
                │  React SPA  │ (Vite, TS)
                │  responsive │
                └──────┬──────┘
                       │ HTTPS / JWT
                ┌──────▼──────┐      ┌────────────┐
                │  FastAPI    ├──────► PostgreSQL │
                │  (capas:    │      └────────────┘
                │  api/svc/   │      ┌────────────┐
                │  repo)      ├──────► Redis      │ (cola: WhatsApp,
                └──────┬──────┘      │ recordat.) └────────────┘
                       │ workers
                ┌──────▼──────────────────────────┐
                │ WhatsApp API · Google Calendar  │
                │ Email/SMS · (MP/AFIP futuro)    │
                └─────────────────────────────────┘
```

Decisión de alto nivel: un solo deploy compone backend + worker + Postgres + Redis (ver `08_arquitectura_propuesta.md`). Sin microservicios: equipo de 3, alcance académico.

## Integraciones externas

| Servicio | Propósito | Tipo |
|---|---|---|
| WhatsApp Business API (Meta) | Recordatorios, confirmación, reserva asistida, lista de espera | REST + webhooks |
| Google Calendar | Sincronización por profesional | REST/OAuth |
| Google (reseñas) | Solicitud automática post-turno | Link/redirect |
| Email/SMS | Fallback de notificaciones | SMTP/SDK |
| Excel/CSV | Importación pacientes, exportación liquidaciones/datos | Archivo |
| MercadoPago / AFIP-ARCA | Cobros y facturación — SOLO escalamiento (post-TP, fuera de v1.0; pagos simulados — decisión 2026-10-05) | REST (futuro) |

## API REST (resumen por recurso)

- `/auth` — login, refresh, perfil.
- `/pacientes` — CRUD + importación Excel/CSV.
- `/profesionales`, `/sillones` — recursos de agenda.
- `/turnos` — CRUD, cambios de estado, confirmación por token (pública), lista de espera.
- `/odontograma`, `/historias`, `/presupuestos` — clínica.
- `/cuentas`, `/caja`, `/recibos` — cobros.
- `/obras-sociales`, `/nomenclador`, `/liquidaciones` — OS + exportación CSV/PDF.
- `/notificaciones` — envío y estado.
- `/admin` — usuarios, roles, aranceles, exportación total.
