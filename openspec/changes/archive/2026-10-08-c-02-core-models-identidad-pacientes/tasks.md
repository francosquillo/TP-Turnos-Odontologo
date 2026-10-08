# Tasks — c-02-core-models-identidad-pacientes

> Convención TDD estricta (Iron Law): cada task de implementación empieza con un
> test en fallo (RED) que falle por la razón esperada, luego GREEN mínimo, luego
> REFACTOR. Orden por dependencias. Chunks ≤ 2 h. Constraints contra Postgres REAL
> del compose (NUNCA SQLite — no soporta EXCLUDE/GiST). Nombres
> `test_<unidad>_<escenario>_<resultado>` (AAA). `freezegun` para tiempos.

## 1. Alembic + base de modelos (infra de migración)

- [x] 1.1 Agregar `alembic` a `requirements.txt` + `alembic.ini` (script_location backend/alembic, sin URL hardcodeada) con test RED de import (`from alembic.config import Config`) que pase en GREEN al instalar, verificado con `pip install -r backend/requirements.txt && python -c "import alembic"`
- [x] 1.2 Crear `backend/alembic/env.py` async (engine desde `DATABASE_URL`, `target_metadata=Base.metadata`, offline/online) + `Base` declarativa en `modelos/__init__.py`, verificado con test RED de import de `Base` y `alembic upgrade head` sin tablas que pase en GREEN
- [x] 1.3 Escribir migración `001_core_identidad_pacientes` (upgrade crea 5 tablas + índices; downgrade las elimina) con test RED `test_migracion_001_sube_y_baja_limpio` contra Postgres real (upgrade→downgrade→upgrade sin error) que pase en GREEN al aplicar la migración

## 2. Rol + Usuario (identidad, FK simple)

- [x] 2.1 Crear `modelos/rol.py` + `modelos/usuario.py` (PK IDENTITY, `rol.nombre` TEXT+CHECK 3 fijos, `usuario.email` TEXT unique + índice `LOWER(email)`, `rol_id` FK NOT NULL + índice manual, `activo` BOOLEAN NOT NULL, `TIMESTAMPTZ`) con test RED `test_crear_usuario_con_rol_valido_persiste` contra PG real que pase en GREEN al crear los modelos
- [x] 2.2 Crear `esquemas/usuario.py` (`extra='forbid'`, sin `password_hash` en response) con test RED `test_esquema_usuario_rechaza_campo_extra` (campo extra → ValidationError) que pase en GREEN al implementar el esquema
- [x] 2.3 Implementar `servicios/usuarios_servicio.py` con guard último-admin (desactivar/eliminar el único admin activo aborta) con test RED `test_deshabilitar_ultimo_admin_bloqueado` (unit con repos mockeados + integración en PG real) que pase en GREEN al implementar el guard
- [x] 2.4 Verificar unicidad email case-insensitive con test RED `test_email_duplicado_case_insensitive_rechazado` contra PG real (`Admin@demo.test` vs `admin@demo.test` → IntegrityError) que pase en GREEN con el índice expresión

## 3. Paciente (CRUD + soft-delete + índices)

- [x] 3.1 Crear `modelos/paciente.py` (dni TEXT nullable + unique parcial `WHERE dni IS NOT NULL`, índices dni/apellido/telefono, `deleted_at` nullable, consentimiento + fecha) con test RED `test_crud_paciente_ficticio_ok` contra PG real que pase en GREEN al crear el modelo
- [x] 3.2 Implementar `repos/paciente_repo.py` (`listar_activos`, `soft_delete` sin DELETE físico) sobre `BaseRepository` con test RED `test_paciente_soft_delete_oculto_en_listado` (eliminado no lista pero fila persiste con `deleted_at`) que pase en GREEN al implementar el repo
- [x] 3.3 Verificar unicidad DNI con test RED `test_dni_duplicado_rechazado_y_nulo_multiple_permitido` contra PG real (mismo DNI → IntegrityError; dos NULL → ok) que pase en GREEN con el índice parcial

## 4. Profesional + Sillón (demo operativa)

- [x] 4.1 Crear `modelos/profesional.py` + `modelos/sillon.py` (`usuario_id` nullable `ON DELETE SET NULL` + índice, `agenda_config` JSONB default `'{}'`, `sillon.nombre` unique, `sede` TEXT default sede única, `activo`) con test RED `test_profesional_demo_agenda_valida` (Pydantic `AgendaConfig` valida slot + franjas) que pase en GREEN al crear los modelos
- [x] 4.2 Crear `esquemas/{profesional,sillon,paciente}.py` (`extra='forbid'`) con test RED de rechazo de campo extra por esquema que pase en GREEN al implementarlos

## 5. Base repository + repos restantes

- [x] 5.1 Crear `repos/base.py` (`BaseRepository[M]` async: get/list/crear/actualizar tipados) + `repos/{rol,usuario,profesional,sillon}_repo.py` que heredan sin duplicar, verificado con test RED `test_repos_heredan_crud_base` (listar pacientes + get sillón vía base genérica) que pase en GREEN al implementar la base
- [x] 5.2 Verificar convenciones de catálogo con test RED `test_convenciones_tipos_en_catalogo` contra PG real (PK bigint+identity, tiempos timestamptz, sin serial/varchar/timestamp-naive en `information_schema`) que pase en GREEN tras la migración 001

## 6. Seed idempotente (demo ficticia)

- [x] 6.1 Implementar `app/db/seed.py` (`seed_roles`, `seed_admin` desde `SEED_ADMIN_*` con fail-fast, `seed_demo` sillón + profesional con `agenda_config` semanal, guardas por clave natural + transacción ordenada) con test RED `test_seed_doble_ejecucion_no_duplica` contra PG real (dos corridas → mismos conteos, sin IntegrityError) que pase en GREEN al implementar el seed
- [x] 6.2 Verificar seed deja demo mínima con test RED `test_seed_deja_roles_admin_sillon_profesional` (3 roles sin `dueno`, 1 admin activo, 1 sillón activo, 1 profesional con agenda válida) que pase en GREEN tras el seed

## 7. Verificación integral GATE 1

- [x] 7.1 Ejecutar suite completa `docker compose up -d db && alembic upgrade head && pytest backend/app/tests` contra Postgres real y verificar que toda la suite (C-01 + C-02) está verde sin ningún test en SQLite — GATE 1 [x] Verificado PG real 2026-10-08: 65 passed, 1 skipped (DB puerto 5433 por PG18 en 5432)
- [x] 7.2 Correr `openspec validate --change c-02-core-models-identidad-pacientes --strict` y verificar que proposal/design/specs/tasks pasan sin errores (corregir lo que el validador reporte)
