# Design — c-12-admin-cierre-demo

## Context

Último change del roadmap. Plazo 08/11/2026; hoy 02/11/2026. Un verify completo del backend
tarda entre 1 h 10 y 1 h 40, así que entran como mucho dos verify completos. Governance
**ALTO**: estas decisiones se revisan antes de `apply`.

Estado real del código (verificado, no supuesto):

- `api/admin.py` (C-03) ya expone `GET /admin/usuarios`, `PATCH /admin/usuarios/:id/desactivar`
  y `DELETE /admin/usuarios/:id`, con el guard `UltimoAdminError` de
  `servicios/usuarios_servicio.py`. No hay alta ni edición.
- El guard lee `listar_admins_activos()` **sin lock**: dos desactivaciones concurrentes de los
  dos únicos admins pueden pasar las dos.
- `DELETE` hace borrado físico. `usuario.id` es referenciado con `ON DELETE RESTRICT` por
  `caja`, `recibo`, `movimiento`, `arancel`, `liquidacion` y otros: hoy un usuario con historial
  produce un `IntegrityError` (500).
- `usuario` no tiene `deleted_at`; la baja lógica es `activo=false`. `get_current_user` y el
  login ya rechazan usuarios inactivos.
- `/aranceles` (C-11) ya tiene alta, cierre de vigencia y lectura, con escritura solo admin,
  precio inmutable y `creado_por`/`cerrado_por`.
- No existe ninguna tabla de auditoría genérica. RN-GL-02 está cubierta por columnas de autor en
  sobreturnos, anulaciones y aranceles; falta "accesos admin".
- `GET /pacientes` es todavía el stub de C-01; no hay alta de pacientes por API salvo la reserva
  online (`reserva_servicio` reutiliza un paciente existente por teléfono).
- `pages/Seguridad.tsx` es un texto fijo; no hay `GET /seguridad` en el backend.
- `PanelAdmin` en `App.tsx` es un placeholder.
- `core/seed_plantillas.py` ya tiene la plantilla `resena_google` con `link_resena`, y el CHECK
  de `notificacion.tipo` ya admite ese tipo. `notificacion_servicio.encolar_confirmacion` es el
  modelo de encolado idempotente (`notif:{turno_id}:{tipo}`).
- `Settings` ya tiene `gcal_client_id` y `gcal_secret`; no hay `GOOGLE_REVIEW_URL`.
- El seed no crea pacientes, turnos, cajas ni recibos.
- `requirements.txt` no tiene `python-multipart`, `openpyxl` ni `pandas`. El frontend no tiene
  `@playwright/test`.
- La exportación de C-11 es sincrónica (`asyncio.to_thread`) y neutraliza fórmulas en CSV.

## Goals / Non-Goals

**Goals**: núcleo presentable primero (seguridad, usuarios, seed y E2E); opcionales en orden de
recorte y cada uno independiente, para poder cortar en cualquier punto sin dejar nada a medias.

**Non-Goals**: CRUD de aranceles nuevo, CRUD general de pacientes, alta de profesionales, OAuth
y sincronización real con Google Calendar, escritura de reseñas, worker para exportaciones,
cifrado en reposo o TLS en el despliegue local.

## Decisions

### D-01 — No construir `CRUD /admin/aranceles` **[a confirmar]**

`CHANGES.md` pide un `CRUD /admin/aranceles` "versión simple, audita cambios RN-GL-02". C-11 ya
lo cubre en `/aranceles`: cada cambio de precio es una fila nueva, cerrar vigencia registra
`cerrado_por`, y no hay borrado. Duplicarlo bajo `/admin` crearía dos caminos para la misma
regla. **Recomendación**: no hacer nada en aranceles. Si se quiere UI de aranceles, es otro
change post-TP.

### D-02 — Alta y edición de usuarios

`POST /admin/usuarios` con `UsuarioAltaIn` (`nombre`, `email`, `password`, `rol` como
`Literal["admin","odontologo","secretaria"]`, `extra='forbid'`). `PATCH /admin/usuarios/:id`
con `UsuarioEdicionIn` de campos opcionales (`nombre`, `rol`, `activo`, `password`). Contraseña
de 8 caracteres o más, hasheada con `hashear_password` (Argon2, igual que el login). Email
repetido → `409`, detectado por `obtener_por_email` y, como red, por el índice único
`uq_usuario_email_lower`. La respuesta es `UsuarioAdminOut` (sin hash).

`PATCH` con `activo=false` se rechaza con `422` y remite a `.../desactivar`, para que haya un
solo camino de baja y un solo lugar del guard. **Recomendación**: así.

Cambiar la contraseña de otro usuario no invalida sus sesiones abiertas: el access dura 30 min y
el refresh rotativo sigue vivo hasta expirar. Se acepta en v1.0 **[a confirmar]**; la
alternativa es revocar sus refresh en Redis (+1 h).

Crear un usuario `odontologo` no crea un `Profesional`; el profesional demo ya está vinculado
por el seed. Se documenta como límite.

### D-03 — Guard del último admin: cambio de rol y concurrencia **[a confirmar]**

- El guard se aplica también cuando `PATCH` cambia el rol de un admin activo a otro rol.
- Concurrencia: `listar_admins_activos` pasa a `SELECT ... FOR UPDATE` sobre las filas de
  admins activos, dentro de la transacción del request. Dos operaciones concurrentes se
  serializan y la segunda ve un solo admin y responde `409`. Test con dos sesiones contra
  Postgres real.

**Recomendación**: hacer las dos; es ~1 h y cierra un hueco real de RN-AU-03.

### D-04 — `DELETE` de usuario con historial → `409` **[a confirmar]**

Se mantiene el borrado físico solo para usuarios sin historial (por ejemplo, uno creado por
error). Con historial, el router captura el `IntegrityError` de FK, hace rollback y responde
`409` "el usuario tiene historial; desactivalo". La UI no ofrece eliminar: solo desactivar y
reactivar. **Recomendación**: así. Alternativa descartada: convertir `DELETE` en baja lógica
(cambia el contrato de C-03 y su spec).

### D-05 — `GET /seguridad`: hechos derivados de la configuración

Router nuevo `api/seguridad.py`, sin dependencia de auth, `def` síncrono (no hace I/O). Arma un
`SeguridadOut` desde `get_settings()` y constantes del código:

- `datos_ficticios: true` y el texto de declaración.
- `hash_contrasenas: "argon2"`, `access_token_min: settings.jwt_expire_min`,
  `refresh_rotativo: true`.
- `whatsapp_modo: "mock" | "real"` desde `whatsapp_mock`; sin datos clínicos en mensajes.
- `google_calendar_habilitado` (mismo cálculo que D-09).
- `auditoria`: lista de lo que de verdad se registra (sobreturnos, anulaciones, aranceles y, si
  entra R3, acciones admin). La lista se arma en el código según exista o no la tabla, para que
  no mienta si R3 se recorta.
- `respaldos`: texto honesto: "volumen Docker local + exportación total" (esta última solo si
  entra R5).
- `cifrado`: `"en tránsito y en reposo: pendiente para producción (RN-GL-03); el despliegue v1.0 es local"`.

`Seguridad.tsx` hace `fetch` a `/seguridad` y lo renderiza; con error muestra un mensaje y no
muestra afirmaciones. Diseño cuidado (es un diferenciador), con copy para pacientes y dueños de
consultorio, en voz activa y sentence case.

### D-06 — Seed demo sin caja ni recibos

Se suma `seed_pacientes_demo`: 4 pacientes ficticios idempotentes por DNI (DNI con prefijo de
prueba, teléfonos `+54 9 11 0000-00xx`, emails `@example.com`). Uno con Plan Base de "OS
Ficticia Demo" y otro con Plan Plus. El seed **no** crea cajas, recibos ni movimientos: una caja
de un día anterior sin cerrar bloquearía la operación de hoy (RN-CO-01), y así la nota de C-10
sobre `clave_idempotencia` (D-25) no aplica. Cajas, recibos y liquidaciones nacen en vivo
durante la demo. Tampoco crea turnos: la demo arranca reservando. **Recomendación**: así.

### D-07 — E2E: prueba API automatizada + recorrido `playwright-cli` **[a confirmar]**

- **Automatizado**: `test_c12_e2e_flujo.py`, contra Postgres real, con el cliente ASGI de los
  tests existentes y Redis de prueba, recorre: reserva con el teléfono del paciente demo con
  plan → confirmar con token → agenda del profesional → `asistido` → hallazgo FDI → presupuesto
  → aceptar (con cobertura) → cobrar en caja → generar y presentar liquidación del mes → cobrar
  la liquidación → cierre de caja con diferencia 0.
- **Manual con evidencia**: `playwright-cli` contra el compose local (`open → goto → snapshot →
  interactuar por refs → snapshot → close`), capturas archivadas con el change.
- No se agrega `@playwright/test` al frontend: suma dependencias, navegadores y tiempo de verify
  a 6 días del plazo.

**Orden del recorrido**: `CHANGES.md` dice "cobrar → cierre → liquidación". Cobrar una
liquidación registra un ingreso en la caja de hoy, y con la caja de hoy cerrada responde `409`
(C-11 D-12). Por eso el recorrido es **cobrar → liquidación (generar, presentar, cobrar) →
cierre**. Alternativa: generar y exportar la liquidación después del cierre, sin cobrarla.

### D-08 — (R1) Reseña Google

`GOOGLE_REVIEW_URL` opcional en `Settings` y en `.env.example`. En el router de cambio de estado,
al pasar a `asistido` con éxito y con la URL presente, se llama `encolar_resena`, hermano de
`encolar_confirmacion`: misma clave idempotente `notif:{turno_id}:resena_google`, misma
validación de teléfono, payload solo con `nombre_pila` y `link_resena`. Si el encolado falla
(Redis caído), se registra y el cambio de estado no se revierte. El envío lo hace el worker
existente. Sin URL, no se hace nada.

### D-09 — (R2) Google Calendar como estado

`GET /integraciones/google-calendar` (cualquier usuario autenticado) devuelve
`{habilitado, mensaje}`. `habilitado` es `bool(gcal_client_id and gcal_secret)`. Aun con
credenciales, v1.0 no sincroniza: el mensaje lo dice. Se muestra en el panel admin y en
`/seguridad`. **Recomendación**: no implementar OAuth; `CHANGES.md` dice "sincronización real
solo si hay creds", pero no hay tiempo ni forma de probarlo sin credenciales reales.

### D-10 — (R3) Auditoría admin

Migración `009_auditoria_admin` encadenada a `008_obras_sociales`: tabla
`evento_auditoria (id identity, actor_id FK usuario RESTRICT, accion text CHECK catálogo,
objeto_tipo text, objeto_id bigint null, detalle jsonb, created_at timestamptz default now())`,
índice por `created_at desc` y por `actor_id`, y trigger `BEFORE UPDATE OR DELETE` que lanza
excepción (mismo patrón que los triggers de inmutabilidad de C-09/C-10). `detalle` nunca lleva
contraseñas ni PHI (por ejemplo, la importación guarda conteos, no filas). Los servicios de
usuarios, importación y exportación agregan el evento con `flush` dentro de la transacción del
router, así un `4xx` con rollback no deja evento. `GET /admin/auditoria?limit&offset`.

Si se recorta R3: `/seguridad` no lista "acciones admin" (D-05) y RN-GL-02 queda parcial,
documentado en el archive.

### D-11 — (R4) Importación de pacientes **[a confirmar]**

- `POST /pacientes/import` (`multipart/form-data`, campo `archivo`), roles `admin` y
  `secretaria` según la matriz de `03`. Requiere `python-multipart`. XLSX con `openpyxl`
  (`read_only=True`), CSV con `csv` estándar. Sin `pandas`.
- Límites: 1 MB y 2000 filas; si se superan, `422` sin crear nada.
- Política **parcial**: se crean las filas válidas y se reportan las inválidas, en una sola
  transacción. Validación previa por fila (campos, formato, DNI repetido en archivo y en base);
  la inserción usa `INSERT ... ON CONFLICT DO NOTHING` sobre `uq_paciente_dni`, y una fila que
  no se inserta por carrera se reporta como DNI existente. Así una fila mala no aborta la
  transacción.
- Teléfono normalizado con la misma función que la reserva online; email con validación simple.
- Respuesta `ImportacionOut {creados, rechazados, errores: [{fila, motivo}]}`; el número de fila
  es el del archivo (encabezado = fila 1).
- Sincrónico: el parseo corre en `asyncio.to_thread`.

**Recomendación**: política parcial. Alternativa: todo o nada (más simple de explicar, peor para
migrar planillas reales).

### D-12 — (R5) Exportación total sincrónica **[a confirmar]**

`CHANGES.md` dice "vía worker". Con datos de demo el ZIP pesa pocos KB, y C-11 ya eligió export
sincrónico (D-17). Un job en worker exige estado del job, almacenamiento del blob fuera de Redis
(>100 KB) y polling en la UI: no entra en el plazo. **Recomendación**: `GET /admin/export-total`
sincrónico, ZIP armado en `asyncio.to_thread` con `zipfile` + `csv`, un CSV por tabla de
`Base.metadata` en orden de dependencias, más `LEEME.txt` con la declaración de datos
ficticios. Se excluyen columnas `password_hash` y cualquier hash de token. Celdas neutralizadas
con la función de C-11.

**Contenido clínico [a confirmar]**: la matriz de `03` no da HC ni odontograma al admin, pero
la exportación total es el camino de RN-GL-01 para el borrado físico y el anti lock-in del dueño.
**Recomendación**: incluir las tablas clínicas, solo admin y (si entra R3) auditado. Alternativa:
excluirlas y declararlo en `LEEME.txt`.

### D-13 — Frontend admin

`features/admin/` con `UsuariosPage` (lista, alta, cambio de rol, desactivar, reactivar),
`api.ts` y `tipos.ts` sin `any`; si entran, `ImportarPacientes` y botón de exportación total.
`PanelAdmin` en `App.tsx` pasa a montar `UsuariosPage` con carga diferida, como las demás
features. Cargas independientes con `Promise.all`.

### D-14 — Capas y archivos

- `api/admin.py`: alta, edición, `409` de FK, auditoría (R3), export (R5).
- `api/seguridad.py` nuevo; `api/integraciones.py` nuevo (R2).
- `servicios/usuarios_servicio.py`: `crear_usuario`, `editar_usuario`, guard ampliado.
- `repos/usuario_repo.py`: lock en `listar_admins_activos`.
- `servicios/importacion_servicio.py` (R4), `servicios/exportacion_servicio.py` (R5),
  `repos/auditoria_repo.py` + `modelos/auditoria.py` (R3).
- Tests nuevos con prefijo `test_c12_*`. Si entra R3, actualizar los tests de cabeza de
  migración de C-08..C-11 y la lista de `test_c05_reserva_pg.py`.

## Risks / Trade-offs

- **Plazo**: el núcleo suma ~13 h y los opcionales ~13 h; con dos verify completos (~3 h) no
  entra todo si aparece un rojo. Mitigación: orden de tasks por valor de demo y cortes limpios.
- **Lock del guard**: `FOR UPDATE` sobre admins agrega espera entre operaciones admin
  simultáneas; irrelevante en volumen de un consultorio.
- **E2E frágil por tiempo**: el flujo usa "hoy" (caja, mes de liquidación). El test fija la
  hora con `freezegun` y una fecha dentro del horario del profesional demo.
- **Reseña** (R1): si el teléfono del paciente demo no es válido para WhatsApp, la notificación
  falla y avisa a secretaría (comportamiento de C-06); en modo mock no se envía nada real.
- **Export con tablas clínicas** (D-12): contradice la letra de la matriz de `03`; queda a
  decisión humana.
- **Cambio de contraseña sin revocar sesiones** (D-02): ventana de hasta 7 días de refresh.

## Migration Plan

Núcleo: sin migraciones. R3: `009_auditoria_admin` con downgrade limpio (drop trigger, función
y tabla). Seed: re-ejecutable sobre bases existentes; solo agrega pacientes demo.

## Open Questions

Las marcadas **[a confirmar]**: D-01, D-02 (revocación de sesiones), D-03, D-04, D-07, D-11 y
D-12 (sincrónico y contenido clínico). Las tasks asumen las recomendaciones.
