# Proposal — c-12-admin-cierre-demo

## Why

C-01..C-11 están archivados, pero el admin todavía no puede dar de alta usuarios ni cambiarles
el rol (solo listar, desactivar y eliminar desde C-03), la página de seguridad es un texto fijo
sin respaldo en el backend, y no hay seed ni recorrido que permitan mostrar el flujo completo
en la demo (US-050, US-051, US-052). Es el último change antes del plazo del 08/11/2026: tiene
que dejar primero un núcleo presentable y dejar lo opcional al final, para poder recortarlo.

Leer antes: `knowledge-base/03_actores_y_roles.md` (RBAC, rutas públicas),
`06_funcionalidades.md` (US-050..052), `05_reglas_de_negocio.md` (RN-GL-01, RN-GL-02, RN-AU-03),
`08_arquitectura_propuesta.md` (seguridad, despliegue, variables de entorno),
`02_descripcion_general.md` (integraciones). Dependencias: C-02 y C-03 (base); el E2E final
usa C-05, C-10 y C-11, todos archivados.

## What Changes

Núcleo (se hace primero):

- `GET /seguridad` público: hechos verificables derivados de la configuración real (datos
  ficticios, Argon2, vida del JWT, modo mock de WhatsApp, estado de Google Calendar, qué se
  audita y cómo se respalda). La página pública `Seguridad` los muestra. Sin afirmaciones que
  el sistema no cumpla (por ejemplo, no declara cifrado en reposo).
- Gestión de usuarios para admin: `POST /admin/usuarios` (alta con rol y contraseña inicial) y
  `PATCH /admin/usuarios/:id` (nombre, rol, reactivar, nueva contraseña). Se mantienen
  `GET`, `PATCH .../desactivar` y `DELETE` de C-03.
- Resguardo del último admin ampliado: también bloquea **quitarle el rol admin** al único admin
  activo, y es seguro ante dos operaciones concurrentes (lock en Postgres).
- `DELETE /admin/usuarios/:id` sobre un usuario con historial (turnos, recibos, cajas,
  aranceles, liquidaciones) responde `409` con el motivo, en vez de un `500` por FK.
- Pantalla de usuarios en el panel admin (reemplaza el placeholder de C-03).
- Seed demo ampliado: pacientes ficticios, uno con plan de "OS Ficticia Demo", listo para
  recorrer el flujo. El seed **no** crea cajas, recibos ni movimientos.
- Prueba E2E del flujo de demo a nivel API sobre Postgres real, y recorrido manual con
  `playwright-cli` contra el compose local: landing → reserva → confirmar → agenda →
  odontograma → presupuesto → cobrar → liquidación → cierre.

Opcional, en orden de recorte (marcado **(R)** en tasks):

- **(R1)** Reseña Google post-turno: al pasar un turno a `asistido` se encola la plantilla
  `resena_google` existente con `GOOGLE_REVIEW_URL`; sin esa variable, deshabilitado.
- **(R2)** Google Calendar: solo estado con flag (`GCAL_CLIENT_ID/SECRET`), sin OAuth ni
  sincronización en v1.0.
- **(R3)** Auditoría de acciones admin (RN-GL-02 "accesos admin"): tabla append-only y
  `GET /admin/auditoria`.
- **(R4)** `POST /pacientes/import` CSV/XLSX con reporte de errores por fila.
- **(R5)** `GET /admin/export-total`: ZIP de CSV, sincrónico.

Fuera de scope, con motivo:

- `CRUD /admin/aranceles`: **no se construye**. C-11 ya expone `/aranceles` (alta, cierre de
  vigencia, precio inmutable, solo admin escribe) y guarda `creado_por` y `cerrado_por`, que
  cubren "cambios de arancel" de RN-GL-02.
- CRUD general de `/pacientes` y alta de profesionales: siguen fuera (el paciente nace por
  reserva, seed o importación).

## Capabilities

### New Capabilities

- `seguridad-publica`: endpoint y página pública con hechos de seguridad verificables y la
  declaración de datos ficticios.
- `admin-usuarios`: alta, edición, reactivación y pantalla de gestión de usuarios para admin.
- `auditoria-admin` **(R3)**: registro append-only de acciones admin y su consulta.
- `datos-import-export` **(R4, R5)**: importación de pacientes con reporte por fila y
  exportación total.
- `integracion-google-calendar` **(R2)**: estado de la integración detrás de un flag.

### Modified Capabilities

- `auth-rbac`: el resguardo del último admin cubre el cambio de rol, la concurrencia y el
  `DELETE` con historial.
- `core-models-identidad-pacientes`: el seed demo suma pacientes ficticios para el recorrido
  E2E, sin caja ni recibos.
- `notificaciones-whatsapp` **(R1)**: encolado de la reseña Google al marcar `asistido`.

## Impact

- Backend: `api/admin.py`, `servicios/usuarios_servicio.py`, `repos/usuario_repo.py`,
  `esquemas/usuario.py`, nuevo `api/seguridad.py`, `db/seed.py`, `core/config.py`
  (`GOOGLE_REVIEW_URL`, opcional). Opcionales: migración `009_auditoria_admin` (R3),
  `api/pacientes.py` (R4), `api/admin.py` export (R5), `servicios/notificacion_servicio.py` (R1).
- Dependencias nuevas solo si entran R4: `python-multipart` (subida de archivos en FastAPI) y
  `openpyxl` (XLSX). No se agrega `pandas`.
- Frontend: `pages/Seguridad.tsx`, nueva `features/admin` (usuarios; importación y exportación
  si entran R4/R5), `App.tsx`.
- Datos: el seed suma pacientes demo idempotentes por DNI. Una migración solo si entra R3.
- Sin pagos reales, sin AFIP, sin datos reales, sede única.
