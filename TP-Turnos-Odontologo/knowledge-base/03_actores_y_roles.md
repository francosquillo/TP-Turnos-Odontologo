# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|---|---|---|
| Paciente | Persona con turno o en lista de espera | Reserva pública web, confirmación/cancelación por WhatsApp o link con token, paga en consultorio |
| Secretaria/recepcionista | Gestiona agenda y caja | SPA autenticada: agenda, turnos, cobros, cierre diario |
| Odontólogo | Atiende y registra clínica | SPA autenticada: odontograma, HC, presupuestos, planes |
| Administrador del sistema (incluye rol Dueño como alias) | Configura el sistema y controla gestión | SPA autenticada: usuarios, roles, aranceles, datos maestros, reportes, liquidaciones, exportaciones |

El paciente **no tiene usuario autenticado** en v1.0: opera vía reserva pública + tokens de un solo uso por WhatsApp/link (sin portal).

> **Decisión 2026-10-05 (IN-01 — RESUELTA)**: Dueño = Admin (mismo rol, alias). No existe rol Dueño separado en v1.0; donde se mencione "dueño" léase Admin con permiso de reportes/liquidaciones.

## RBAC — Matriz de permisos

| Recurso | Admin (incl. Dueño como alias) | Odontólogo | Secretaria |
|---|---|---|---|---|
| Usuarios/roles | CRUD | — | — |
| Pacientes | CRUD + importar | Ver + editar clínica | CRUD + importar |
| Agenda/turnos | CRUD | Ver propios + gestionar | CRUD |
| Odontograma/HC | — | CRUD propios | Ver |
| Presupuestos | Ver | CRUD | Ver + cobrar |
| Caja/cierre | Ver + anular | — | Cobrar + cierre |
| Liquidaciones OS | CRUD + exportar | Ver | — |
| Reportes/exportación total | Sí | Propios | — |

Roles fijos v1.0 (3): `admin` (incl. alias Dueño), `odontologo`, `secretaria`. Un usuario tiene un solo rol (`usuario.rol_id` FK — ver `04`; decisión IN-02 del 2026-10-05).

## Rutas públicas

- `GET /` landing + `POST /reservas` (reserva online sin login).
- `GET /confirmar/:token` — confirmar/cancelar turno (token un solo uso, expira).
- `GET /disponibilidad` — huecos por profesional/fecha.
- `POST /webhooks/whatsapp` — eventos de Meta (firmado).
- `GET /seguridad` — página pública de seguridad documentada.
- `POST /auth/login`, `POST /auth/refresh`.
