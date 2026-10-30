# Tasks — c-08-clinica-odontograma-hc

> Convención TDD estricta: cada task empieza con un test en fallo por la razón
> esperada (RED), sigue con el mínimo código (GREEN) y termina con REFACTOR en
> verde. Chunks ≤ 2 h, en orden de dependencias. Constraints siempre contra
> **Postgres real** del compose, NUNCA SQLite. `freezegun` para `fecha` y
> `updated_at`. Nombres `test_<unidad>_<escenario>_<resultado>` (AAA). Datos 100%
> ficticios. Sin PHI en logs. Esquemas `extra='forbid'`. TS sin `any`.
>
> Docker: pedir permiso explícito antes de iniciar Docker Desktop y levantar
> `db+redis`; bajarlos al cerrar (reglas duras). Puerto alternativo si PG18 ocupa
> 5432: `POSTGRES_PORT=5433` y `DATABASE_URL_TEST` acorde.

## 1. Modelos y migración 005 (D-01..D-06, D-10)

- [x] 1.1 Capturar la línea base antes de tocar nada: correr `pytest` y los tests de frontend, anotar el conteo y reportar sin arreglar cualquier falla previa. Verificar que `alembic heads` da solo `004_espera`
- [x] 1.2 Crear `modelos/hallazgo_odontograma.py` con `EstadoHallazgoCatalogo` (`UNIQUE (codigo, version)`, CHECK de `alcance`, constante `CATALOGO_ESTADOS_V1` con 7 estados) y `modelos/tratamiento.py` (`codigo` UNIQUE, `precio_base NUMERIC(12,2) CHECK >= 0`), más el helper de carga del catálogo en `db_utils.py`. RED en `test_c08_modelos.py`: `test_catalogo_codigo_version_duplicado_rechazado`, `test_tratamiento_codigo_duplicado_rechazado`, `test_tratamiento_precio_negativo_rechazado` (PG real)
- [x] 1.3 Crear `modelos/historia_clinica.py` (`paciente_id` UNIQUE FK RESTRICT, `ck_hc_baja_con_motivo`, CHECK de longitudes) y exportar en `modelos/__init__.py`. RED: `test_hc_paciente_duplicado_rechazado`, `test_hc_duplicada_aun_con_baja_rechazada`, `test_hc_baja_sin_motivo_rechazada` (PG real)
- [x] 1.4 Sumar `HallazgoOdontograma` con `ck_hallazgo_pieza_fdi_valida`, `ck_hallazgo_cara_catalogo`, `ck_hallazgo_cara_arcada`, `ck_hallazgo_baja_con_motivo`, FK compuesta al catálogo, FK RESTRICT y los 4 índices de D-05. RED parametrizado en PG real: las 32 piezas válidas pasan; 10, 19, 20, 29, 30, 39, 40, 49, 51 y 85 fallan. Además `test_hallazgo_palatina_inferior_rechazada`, `test_hallazgo_lingual_superior_rechazada`, `test_hallazgo_estado_fuera_de_catalogo_rechazado`, `test_hallazgo_segunda_correccion_rechazada`, `test_hc_con_hallazgos_no_se_borra_fisicamente`
- [x] 1.5 Escribir `alembic/versions/005_clinica.py` (`down_revision = "004_espera"`, tablas, `bulk_insert` del catálogo V1, downgrade completo). RED en `test_c08_migracion.py`: `test_c08_cabeza_unica_005_sobre_004`, `test_c08_migracion_declara_checks_e_indices_del_modelo`, `test_c08_catalogo_migracion_igual_a_constante`, `test_c08_upgrade_carga_catalogo_sin_seed`, `test_c08_downgrade_upgrade_limpio` (PG real con Alembic)
- [x] 1.6 Ajustar tests por la cabeza nueva: `test_c07_migracion.py` (validar `004_espera` en la cadena y cabeza única), `test_c05_reserva_pg.py` (sumar `005_clinica.py`) y `db_utils.reset_estado_base` (sumar las 4 tablas). Verificar con la suite completa de migraciones y `test_c02_alembic.py` en verde

## 2. Esquemas (D-02, D-03, D-08)

- [x] 2.1 Crear en `esquemas/clinica.py` el tipo `PiezaFdi`, el literal `Cara`, `HistoriaIn`, `HistoriaPatch`, `HistoriaOut`, `BajaIn` y `TratamientoOut`, todos `extra='forbid'`. RED en `test_c08_esquemas.py`: FDI parametrizado, `test_historia_alergias_vacias_normalizan_a_null`, `test_historia_campo_extra_422`, `test_baja_sin_motivo_invalida`
- [x] 2.2 Sumar `HallazgoIn`, `HallazgoCorreccionIn`, `HallazgoOut`, `HallazgoConAlergias`, `HallazgosConAlergias` y `CatalogoOut`, con la validación de arcada. RED: `test_hallazgo_palatina_pieza_36_invalida`, `test_hallazgo_lingual_pieza_16_invalida`, `test_hallazgo_con_profesional_id_invalido`, `test_hallazgo_con_fecha_invalido`, `test_hallazgo_con_catalogo_version_invalido`, `test_correccion_sin_motivo_invalida`

## 3. Repos (D-05, D-07)

- [x] 3.1 Crear `repos/historia_repo.py` (`activa_por_id`, `por_paciente` incluida baja, `soft_delete`) y `repos/tratamiento_repo.py` (`listar` por `codigo`). RED en `test_c08_repos.py` (PG real): `test_historia_con_baja_no_es_activa`, `test_por_paciente_devuelve_baja_para_distinguir_409`, `test_tratamientos_ordenados_por_codigo`
- [x] 3.2 Crear `repos/hallazgo_repo.py` (listado por `hc_id` con filtros `pieza` e `incluir_anulados`, orden `fecha DESC, id DESC`, `estados_vigentes`) con `freezegun`. RED: `test_historial_pieza_mas_reciente_primero`, `test_listado_excluye_anulados_por_defecto`, `test_historial_incluye_anulados_si_se_pide`, `test_hallazgo_no_se_filtra_a_otra_hc`, `test_estados_vigentes_solo_ultima_version`
- [x] 3.3 Sumar `TurnoRepository.existe_vinculo(profesional_id, paciente_id)` sin alterar métodos existentes. RED (PG real): `test_vinculo_turno_asistido_true`, `test_vinculo_turno_futuro_true`, `test_vinculo_solo_cancelado_false`, `test_vinculo_otro_profesional_false`

## 4. Servicio clínico (D-04..D-08)

- [x] 4.1 Crear `servicios/clinica_servicio.py` con acceso (`exigir_lectura`, `exigir_escritura`) y errores de dominio. RED en `test_c08_servicio.py`: secretaria lee, secretaria no escribe, odontólogo vinculado, sin vínculo, solo turnos cancelados, sin `Profesional` vinculado
- [x] 4.2 Implementar crear, actualizar y dar de baja HC. RED: `test_crear_hc_paciente_inexistente`, `test_crear_hc_paciente_eliminado`, `test_crear_hc_duplicada_conflicto`, `test_crear_hc_con_baja_conflicto_distinto`, `test_patch_solo_campos_enviados_y_avanza_updated_at` (`freezegun`), `test_baja_hc_conserva_hallazgos`
- [x] 4.3 Implementar registrar hallazgo: autor desde el usuario, `fecha` del reloj, versión vigente, regla alcance/cara. RED: `test_ausente_en_mesial_invalido`, `test_ausente_pieza_completa_ok`, `test_caries_oclusal_ok`, `test_estado_desconocido_invalido`, `test_estado_de_version_no_vigente_invalido`, `test_hallazgo_sella_autor_fecha_y_version`, `test_version_nueva_conserva_hallazgos_v1`
- [x] 4.4 Implementar corregir y dar de baja hallazgo, solo por el autor, en transacción. RED: `test_correccion_baja_original_y_crea_con_corrige_a`, `test_correccion_de_anulado_conflicto`, `test_correccion_de_otro_autor_prohibida`, `test_correccion_concurrente_conflicto` (UNIQUE parcial en PG real), `test_baja_repetida_conflicto`, `test_hallazgo_de_otra_hc_no_encontrado`

## 5. Routers (D-07..D-09)

- [x] 5.1 Crear `api/tratamientos.py` y `GET /odontograma/catalogo` en `api/odontograma.py`, registrar en `main.py`. RED en `test_c08_api.py`: los 3 roles obtienen `200`, sin Bearer `401`, `POST /tratamientos` `405`, catálogo con versión y estados; `test_routers.py` sigue verde con el stub `/clinica`
- [x] 5.2 Crear `api/historias.py` (`GET ?paciente_id`, `GET /:id`, `POST`, `PATCH`, `POST /:id/baja`), con el router como dueño del commit. RED: matriz completa de roles, `paciente_id` faltante `422`, lista vacía `200`, duplicada `409`, `404` tras la baja, `DELETE` `405`, campo extra `422`
- [x] 5.3 Completar `api/odontograma.py` (`GET` lista, `POST`, `GET /:id`, `PUT /:id`, `POST /:id/baja`). RED: `alergias` en la raíz en las 5 respuestas, `?pieza=30` `422`, HC con baja `404`, `403` de admin, secretaria y no autor, corrección `200` con `id` nuevo
- [x] 5.4 Probar con `alergias: null` y con texto en cada respuesta de `/historias` y `/odontograma/:hc_id/hallazgos`, y en `test_c08_openapi` que no hay `DELETE` ni escrituras de catálogo en la especificación generada

## 6. Seed demo (D-10, D-11)

- [x] 6.1 Sumar `seed_tratamientos` a `db/seed.py` (6 tratamientos ficticios, idempotente por `codigo`, no pisa filas). RED: `test_seed_tratamientos_idempotente`, `test_seed_no_pisa_precio_existente` (PG real)
- [x] 6.2 Sumar `seed_usuarios_demo` (`odontologo` y `secretaria`, contraseña desde `SEED_ADMIN_PASSWORD` con Argon2). RED: `test_seed_usuarios_demo_idempotente`, `test_seed_vincula_profesional_demo`, `test_seed_respeta_vinculo_existente`, `test_seed_sin_password_falla`. Verificar `test_c02_seed.py` y `test_c03_seed.py` en verde

## 7. Sin PHI en logs (D-12)

- [x] 7.1 Crear `test_c08_sin_phi.py` con `caplog` en DEBUG y marcadores ficticios en antecedentes, alergias y motivos, cubriendo alta, patch, baja, corrección y `422`, y comprobar que ninguno aparece. Corregir cualquier fuga encontrada

## 8. Frontend `features/odontograma` (D-13)

- [x] 8.1 Crear `tipos.ts` (uniones estrictas, cuadrantes en orden clínico, `carasPermitidas(pieza, alcance)`, `estadoVigente(hallazgos)`, rótulo "Incisal" en incisivos y caninos). RED en `tipos.test.ts`: orden 18→11 / 21→28 / 48→41 / 31→38, 32 piezas, palatina fuera en inferiores, `ausente` solo `pieza_completa`, `pieza_completa` reciente tapa caras antiguas, cara reciente sobre `pieza_completa` antigua
- [x] 8.2 Crear `api.ts` con `fetchConAuth` y guardas de tipo, sin `any` (patrón `features/lista-espera/api.ts`). RED en `api.test.ts`: búsqueda por paciente, alta, corrección con `id` nuevo, `403`/`409`/`422` como `ApiError`, respuesta inesperada rechazada
- [x] 8.3 Crear `AlergiasAviso.tsx` y `OdontogramaPage.tsx` (carga con `Promise.all`, sin HC, abrir HC, edición de antecedentes y alergias). RED: aviso con texto, aviso "no relevadas", aviso visible con detalle abierto, secretaria sin HC ve mensaje y odontólogo ve "Abrir historia"
- [x] 8.4 Crear `Grilla.tsx` y `styles/odontograma.css` solo con `var(--...)` de `tokens.css`, sin colores literales y sin tocar `tokens.css`. RED: render de 32 botones con `aria-label`, estado en texto, sin 19/20/29/30/39/40, test que falla si el CSS tiene literales `#` o `rgb(`. Verificar 390 px y 1440 px en navegador
- [x] 8.5 Crear `PiezaDetalle.tsx` y `HallazgoForm.tsx` (historial con anulados, alta, corrección y baja con motivo). RED: orden del historial, anulado con motivo visible, formulario filtra caras por pieza y estado, secretaria sin controles, odontólogo ve baja solo en hallazgos propios, error de API mostrado con `role="alert"`
- [x] 8.6 Integrar: `React.lazy` en `App.tsx`, página `odontograma`, botón en `TurnoCard` para `odontologo` y `secretaria`, CSS en `main.tsx`. RED en `App.test.tsx` y `AgendaPage.test.tsx`: la agenda abre el odontograma con el paciente correcto y admin no ve el botón. Más `test_odontograma_sin_console` sobre `features/odontograma`. `tsc` limpio

## 9. Verificación integral (hacia C-09)

- [x] 9.1 Escribir `test_c08_flujo3.py` (PG real): odontólogo con turno `asistido` abre HC, carga alergias, registra caries en 16 oclusal, luego obturación, corrige un error, da de baja otro; el historial de 16 muestra todo; la secretaria lee y no escribe; el admin recibe `403`; `GET /tratamientos` devuelve datos del seed
- [x] 9.2 Con permiso explícito y Docker en marcha, correr `alembic upgrade head`, la suite backend completa con `pytest`, tests y `tsc` de frontend, build y comparar con la línea base de 1.1. Bajar `docker compose down` sin `-v` y cerrar Docker Desktop
- [x] 9.3 Correr `openspec validate c-08-clinica-odontograma-hc --strict` y `openspec validate --all --strict`, y verificar 0 errores

## Workflow follow-up

- Revisar D-06, D-07, D-11 y D-14 antes de empezar el apply.
- Corregir "Migración 003" en `CHANGES.md` al archivar y marcar `[x]` C-08.
- Registrar en C-09 las reglas de D-10 sobre hallazgos dados de baja o corregidos.
- Archivar con `/opsx:archive` tras el `verify` en verde.
