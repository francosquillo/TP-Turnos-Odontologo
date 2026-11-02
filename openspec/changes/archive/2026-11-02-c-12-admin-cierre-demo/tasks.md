# Tasks — c-12-admin-cierre-demo

> **Governance ALTO**: estas tasks asumen las recomendaciones de D-01, D-02, D-03, D-04, D-07,
> D-11 y D-12 de `design.md`. Confirmarlas antes de empezar; si alguna cambia, actualizar specs,
> design y tasks.
>
> **TDD estricto**: en cada task, primero el test en RED por la razón esperada, después el
> mínimo código en GREEN. Postgres real para constraints, locks y concurrencia; `freezegun` para
> tiempos. Cada task dura 2 h como máximo.
>
> Antes de tocar `api/admin.py`, `usuarios_servicio.py`, `seed.py` o el cambio de estado de
> turnos, capturar el baseline de los tests de C-02, C-03, C-04 y C-06 que los cubren. Si alguno
> falla, frenar y reportar.
>
> **Orden**: secciones 1–4 son el núcleo de la demo. Secciones 5–9 son opcionales **(R)**, en
> orden de recorte: se corta primero R1 (sección 5), después R2, R3, R4 y por último R5.
> Cada sección opcional es independiente y se puede cortar sin dejar nada a medias. Las horas
> son estimadas e incluyen RED y GREEN.

## 1. Seguridad pública (núcleo, ~2,5 h)

- [x] 1.1 RED `test_c12_seguridad.py`: `GET /seguridad` sin token responde `200` con `datos_ficticios=true`; `access_token_min` sigue a `JWT_EXPIRE_MIN` (monkeypatch 15); el cuerpo no contiene los valores de `JWT_SECRET`, `WHATSAPP_TOKEN` ni `GCAL_SECRET`; no declara cifrado en reposo ni TLS activos. GREEN: `esquemas/seguridad.py` (`extra='forbid'`), `api/seguridad.py` y registro en `main.py` (D-05). Verificar con pytest. (~1 h)
  - Hecho: 13 tests en verde (`test_c12_seguridad.py`, sin Postgres).
- [x] 1.2 RED `Seguridad.test.tsx`: renderiza los hechos de un `fetch` simulado; con error muestra mensaje y ninguna afirmación. GREEN: `pages/Seguridad.tsx` con fetch tipado, sin `any`, diseño y copy de D-05. Verificar con vitest y `tsc --noEmit`. (~1,5 h)
  - Hecho: 4 tests vitest en verde y `tsc --noEmit` limpio.

## 2. Usuarios: backend (núcleo, ~3 h)

- [x] 2.1 RED `test_c12_usuarios_api.py`: `POST /admin/usuarios` válido → `201` sin hash y el usuario puede loguearse; email repetido con otras mayúsculas → `409`; rol `duenio`, campo extra o contraseña de 7 caracteres → `422`; secretaria u odontólogo → `403`. GREEN: `UsuarioAltaIn`, `crear_usuario` y endpoint (D-02). (~1,5 h)
  - Hecho con repos falsos (`test_c12_usuarios_api.py`, sin Postgres). La variante contra el repo real (indice unico, `rol` relacional) queda cubierta por los tests PG de 2.3: NO EJECUTADOS sin Postgres.
- [x] 2.2 RED: `PATCH /admin/usuarios/:id` reactiva (`activo=true` → puede loguearse), cambia rol (la llamada siguiente se autoriza con el rol nuevo), cambia contraseña (la vieja falla, la nueva entra), `activo=false` → `422`, id inexistente → `404`. GREEN: `UsuarioEdicionIn`, `editar_usuario` y endpoint. (~1 h)
  - Hecho con repos falsos (mismo archivo).
- [x] 2.3 RED `test_c12_ultimo_admin.py` contra Postgres real: quitar el rol admin al único admin activo → `409` y sigue admin; dos desactivaciones concurrentes de los dos únicos admins (dos sesiones) → una `200`, otra `409`, queda un admin; `DELETE` de un usuario con turno o recibo → `409` y nada se borra; `DELETE` de un usuario sin historial → `204`. GREEN: guard en cambio de rol, `FOR UPDATE` en `listar_admins_activos`, captura de `IntegrityError` con rollback (D-03, D-04). Suite C-03 de último admin en verde. (~1,5 h)
  - Pendiente de ejecución: el código y los tests están escritos (9 tests con repos falsos en verde; 6 tests contra Postgres real NO EJECUTADOS por falta de Postgres: ver `test_c12_ultimo_admin.py::test_pg_*`). No se marca `[x]` hasta correrlos.

## 3. Usuarios: pantalla (núcleo, ~2,5 h)

- [x] 3.1 RED `features/admin/UsuariosPage.test.tsx`: lista nombre, email, rol y estado; alta con formulario; cambio de rol; desactivar y reactivar; ante `409` del último admin muestra el motivo del backend y la fila sigue activa. GREEN: `features/admin/{UsuariosPage.tsx,api.ts,tipos.ts}` (D-13). Verificar con vitest y `tsc --noEmit`. (~2 h)
  - Hecho: 10 tests vitest en verde (`UsuariosPage.test.tsx`) y `tsc --noEmit` limpio.
- [x] 3.2 Montar `UsuariosPage` en `PanelAdmin` con carga diferida y `RequireRole roles=["admin"]`. Test: una secretaria ve "sin permiso". Verificar con vitest. (~0,5 h)
  - Hecho: `App.admin.test.tsx` (3 tests): admin ve la lista; secretaria y odontólogo ven "sin permiso" y no se pide `/admin/usuarios`.

## 4. Seed demo y E2E (núcleo, ~5 h)

- [x] 4.1 RED `test_c12_seed.py` contra Postgres real: en base limpia existe un paciente demo con plan de "OS Ficticia Demo" y teléfono ficticio válido; no hay cajas, movimientos de caja ni recibos; doble ejecución deja iguales los conteos, pacientes incluidos. GREEN: `seed_pacientes_demo` idempotente por DNI y conteo de pacientes en `run_seed` (D-06). Actualizar el test de doble ejecución de C-02. (~1,5 h)
  - Pendiente de ejecución: `seed_pacientes_demo` + `pacientes` en `run_seed` y `test_c02_seed.py` actualizado; 3 tests de datos del seed en verde sin Postgres; 4 tests contra Postgres real NO EJECUTADOS (`test_c12_seed.py::test_pg_*`). No se marca `[x]` hasta correrlos.
- [x] 4.2 RED/GREEN `test_c12_e2e_flujo.py` contra Postgres real y Redis de prueba, con `freezegun` en un día y hora del horario demo: reserva con el teléfono del paciente demo con plan → confirmar con token → agenda → `asistido` → hallazgo → presupuesto → aceptar → cobrar → generar, presentar y cobrar liquidación → cierre de caja con diferencia 0 (orden de D-07). Si algún paso falla por un defecto de C-04..C-11, frenar y reportar antes de corregir. (~2 h)
  - Pendiente de ejecución: `test_c12_e2e_flujo.py` escrito (usa `FakeStore` como Redis de prueba), NO EJECUTADO por falta de Postgres. Sin verificar contra el stack real.
- [x] 4.3 Recorrido manual con `playwright-cli` contra el compose local recién sembrado: landing → reserva → confirmar → agenda → odontograma → presupuesto → cobrar → liquidación → cierre, más Seguridad y Usuarios. Guardar capturas en `openspec/changes/c-12-admin-cierre-demo/verify/`. Requiere Docker: pedir permiso según las reglas duras. (~1,5 h)
  - Hecho 2026-11-02 con `playwright-cli` (Chromium) contra API en host + Vite + Postgres/Redis del compose, base `turnos_demo` recién migrada (001-009) y sembrada. Capturas `verify/01-landing.png` a `verify/20-admin-usuarios.png` (landing, reserva, confirmar, agenda, asistido, odontograma, presupuesto, cobrar, recibo, caja, liquidación generada/presentada/cobrada, cierre con diferencia 0, Seguridad, Usuarios). Hallazgos: horarios en UTC (Reservas.tsx y agenda/tipos.ts), `/confirmar` consumido dos veces por StrictMode en dev (UI muestra "venció" aunque el turno quedó confirmado), `/health` postgres=down con DSN `+asyncpg`.
  - Pendiente: requiere el stack vivo y permiso explícito (fase de verify); no se hizo en este apply.

## 5. (R1) Reseña Google post-turno (~2 h) — primero en recortarse

- [ ] 5.1 RED `test_c12_resena.py` contra Postgres real: con `GOOGLE_REVIEW_URL` y marcado `asistido` existe una notificación `resena_google` con el link y sin datos clínicos; un segundo encolado no duplica; sin URL no se crea nada y el turno queda `asistido`; con Redis caído el estado igual cambia. GREEN: `google_review_url` en `Settings` y `.env.example`, `encolar_resena` y llamada desde el cambio de estado (D-08). Suite C-06 en verde. (~2 h)
  - Diferido: fuera del alcance entregado (plazo 08/11/2026), decisión del usuario.

## 6. (R2) Google Calendar como estado (~1 h)

- [ ] 6.1 RED `test_c12_gcal.py`: sin credenciales → `habilitado=false` con mensaje; con las dos → configurado, sin sincronización y sin valores; sin token → `401`. GREEN: `api/integraciones.py` (D-09); mostrarlo en el panel admin y en `/seguridad`. Verificar con pytest y vitest. (~1 h)
  - Diferido: fuera del alcance entregado (plazo 08/11/2026), decisión del usuario.

## 7. (R3) Auditoría admin (~3 h)

- [x] 7.1 RED `test_c12_migracion.py`: `009_auditoria_admin` es la única cabeza sobre `008_obras_sociales`; upgrade y downgrade limpios; `UPDATE` y `DELETE` sobre un evento fallan en Postgres. Actualizar los tests de cabeza de C-08..C-11 y la lista de `test_c05_reserva_pg.py`. GREEN: modelo `auditoria.py` y migración con trigger (D-10). (~1,5 h)
  - Pendiente de ejecución parcial: modelo `EventoAuditoria`, migración `009_auditoria_admin` y tests de cabeza actualizados (C-08..C-11, `test_c05_reserva_pg.py`, `db_utils.reset_estado_base`); los 4 tests estáticos de `test_c12_migracion.py` y los de cabeza en verde; 3 tests contra Postgres real NO EJECUTADOS (upgrade/downgrade con trigger, UPDATE/DELETE rechazados, CHECK de acción).
- [x] 7.2 RED: alta, edición, desactivación y eliminación de usuario registran un evento sin contraseña; un `409` del último admin no registra; `GET /admin/auditoria` ordena del más reciente y pagina; secretaria → `403`. GREEN: `auditoria_repo.py`, llamadas en `usuarios_servicio` y endpoint. Actualizar la lista de auditoría en `/seguridad` y su test. (~1,5 h)
  - Pendiente de ejecución parcial: `auditoria_repo.py`, `auditoria_servicio.py`, llamadas en `usuarios_servicio`, importación y exportación, `GET /admin/auditoria` y línea en `/seguridad`; probado con repos falsos en `test_c12_auditoria.py`; 3 tests contra Postgres real NO EJECUTADOS (`test_pg_*`: orden/paginación del repo real, alta auditada vs 409 sin evento, borrado de un actor con eventos).

## 8. (R4) Importación de pacientes (~4,5 h)

- [x] 8.1 Agregar `python-multipart` y `openpyxl` con versión fija a `requirements.txt`; verificar que se instalan en la imagen del compose. (~0,5 h)
  - Parcial: `python-multipart==0.0.20` y `openpyxl==3.1.5` fijados en `requirements.txt` e instalados en el Python local (los tests corren). FALTA verificar la instalación en la imagen del compose: hay que reconstruir la imagen `api` (no autorizado en esta fase).
- [x] 8.2 RED `test_c12_importacion.py` (servicio, Postgres real): CSV con 3 válidas, una sin apellido y una con DNI repetido en el archivo → 3 creadas y 2 errores con número de fila; DNI existente activo → fila rechazada y paciente intacto; teléfono mal formado → rechazada; XLSX equivalente → mismo resultado; sin columna `apellido`, más de 2000 filas o más de 1 MB → error sin crear nada. GREEN: `importacion_servicio.py` (D-11). (~2 h)
  - Pendiente de ejecución parcial: parseo, validación, reporte y límites con repo falso en verde (`test_c12_importacion.py`, 29 tests incl. API); 3 tests contra Postgres real NO EJECUTADOS (`test_pg_*`: ON CONFLICT con DNI activo y dado de baja).
- [x] 8.3 RED: `POST /pacientes/import` multipart para admin y secretaria → `200` con el reporte; odontólogo → `403`; formato no CSV ni XLSX → `422`. GREEN: endpoint en `api/pacientes.py` y, si entró R3, evento con conteos. (~1 h)
  - Endpoint `POST /pacientes/import` hecho y probado con repo falso (200/403/401/422); falta ejecutar `test_pg_endpoint_importa_y_confirma` contra Postgres. Evento de auditoría: ver 7.2.
- [x] 8.4 RED/GREEN `ImportarPacientes.test.tsx`: sube un archivo y muestra creados, rechazados y la tabla de errores por fila. Verificar con vitest y `tsc --noEmit`. (~1 h)
  - Hecho: 4 tests vitest (`ImportarPacientes.test.tsx`) y `tsc --noEmit` limpio; montado en `PanelAdmin`.

## 9. (R5) Exportación total (~2,5 h)

- [x] 9.1 RED `test_c12_export_total.py` contra Postgres real: admin recibe un ZIP con CSV de pacientes, turnos, presupuestos, movimientos, recibos y cajas que coinciden con la base, más `LEEME.txt`; el CSV de usuarios no tiene `password_hash`; una celda que empieza con `=` sale neutralizada; secretaria → `403`. GREEN: `exportacion_servicio.py` y endpoint (D-12, con la decisión sobre tablas clínicas aplicada); si entró R3, evento de exportación. (~2 h)
  - Pendiente de ejecución: servicio, endpoint y 9 tests sin Postgres en verde (columnas sin hash, neutralización, ZIP, 403/401, cabeceras); 4 tests contra Postgres real NO EJECUTADOS (`test_c12_export_total.py::test_pg_*`: ZIP vs base, sin hash, celda `=`, 403). Evento de exportación: ver 7.2.
- [x] 9.2 Botón de descarga en el panel admin con test de vitest que verifica la llamada y el nombre del archivo; actualizar el texto de respaldos en `/seguridad`. (~0,5 h)
  - Hecho: `ExportacionTotal.test.tsx` (4 tests), `PanelAdmin` monta usuarios + exportación; `/seguridad` agrega la línea de exportación total solo si existe el módulo (test en `test_c12_seguridad.py`).

## 10. Cierre

- [x] 10.1 Verify `full` con `tp-verify-docker` (alembic, pytest backend, vitest, `tsc`, `openspec validate --all --strict`), con permiso explícito para Docker. Registrar totales. (~1,5 h)
  - Verify full 2026-11-02 en una sola corrida, previo a las correcciones de la sección 11: backend 1484/1484, vitest 421/421, tsc y build OK, migración limpia 001→009, seed idempotente, `openspec validate --all --strict` 15/15. Tras la sección 11 se corrieron solo los tests de lo tocado (test_health, vitest completo 50 archivos, tsc) por decisión del usuario, sin repetir el full.
- [x] 10.2 Actualizar `CHANGES.md` (estado de C-12, secciones recortadas y por qué) y, si cambió el seed o las rutas públicas, `knowledge-base/` correspondiente. Verificar que `openspec validate --all --strict` sigue en verde. (~0,5 h)
  - Hecho 2026-11-02: `CHANGES.md` (estado de C-12 con secciones 5 y 6 diferidas) y `knowledge-base/04_modelo_de_datos.md` (seed: paciente demo con plan "OS Ficticia Demo", sin cajas ni recibos). Rutas públicas sin cambios: `GET /seguridad` ya estaba en `03`.

## 11. Correcciones del recorrido de la demo

- [x] 11.1 Horas en UTC en vez de America/Argentina/Buenos_Aires (reserva y agenda mostraban 3 h de más). RED vitest con formateador compartido `shared/fecha.ts`; GREEN: `Reservas.tsx` y `agenda/tipos.ts` lo usan.
- [x] 11.2 `Confirmar.tsx` pedía `GET /confirmar/<token>` dos veces bajo StrictMode (200 y luego 410, "El link venció"). RED: una carga hace un solo request aunque el efecto corra dos veces; GREEN: promesa compartida por token.
- [x] 11.3 `/health` informaba `postgres: down` por pasar `postgresql+asyncpg://` a asyncpg. RED: test de normalización de URL; GREEN: `check_postgres` normaliza el esquema.
- [x] 11.4 Tras marcar "Asistido" la agenda mostraba "Paciente 1 · Sillón 1": `PATCH /turnos/{id}/estado` devuelve `TurnoOut` sin nombres y el frontend reemplazaba la fila. RED/GREEN en el frontend: conservar los nombres de la fila previa al fusionar la respuesta.
- [x] 11.5 `/seguridad` para admin sin lista de eventos de auditoría. Revisado contra specs `seguridad-publica` y `auditoria-admin`: no se exige (la página pública lista QUÉ se audita; los eventos viven en `GET /admin/auditoria`). Sin cambios de código.
