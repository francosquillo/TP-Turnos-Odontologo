# Proposal — c-08-clinica-odontograma-hc (C-08 `clinica-odontograma-hc`)

> Nota de nombre: el change canónico en `CHANGES.md` es `C-08 clinica-odontograma-hc`.
> El CLI `openspec` exige kebab-case minúsculas, por eso el directorio es
> `openspec/changes/c-08-clinica-odontograma-hc/`. Ambos nombres refieren al mismo change.

## Why

El sistema ya cubre turno → asistencia (C-04..C-07), pero al llegar al sillón
(Flujo 3) el odontólogo no tiene dónde registrar nada: `api/clinica.py` sigue
siendo el stub de C-01. Este change crea la historia clínica, el odontograma
FDI y el catálogo de tratamientos (US-020, US-021; RN-CL-03, RN-CL-04,
RN-GL-01). Además es el contrato del que depende C-09: cada ítem de presupuesto
referencia un hallazgo y un tratamiento (RN-CL-01), y C-09 está en el camino
crítico.

## What Changes

- Modelos nuevos: `HistoriaClinica`, `HallazgoOdontograma`, `EstadoHallazgoCatalogo`
  (catálogo cerrado versionado) y `Tratamiento`.
- Migración `005_clinica` sobre `004_espera`. `CHANGES.md` dice "Migración 003":
  está desactualizado (001..004 ya existen). Índice `(hc_id, pieza_fdi)`.
- Notación FDI exacta: solo 11–18, 21–28, 31–38 y 41–48. "11–48" no es un rango
  contiguo: 19, 20, 29, 30, 39 y 40 se rechazan en esquema y en DB.
- Hallazgos que no se sobrescriben: una corrección da de baja la fila anterior y
  crea otra, así el historial por pieza conserva todo.
- Baja lógica de HC y de hallazgos, siempre con motivo (RN-GL-01).
- Endpoints: `CRUD /historias`, `CRUD /odontograma/:hc_id/hallazgos`,
  `GET /tratamientos` y `GET /odontograma/catalogo` (necesario para que la UI no
  duplique el catálogo). Las alergias viajan en toda respuesta clínica.
- Permisos según la matriz de `03_actores_y_roles.md`: odontólogo escribe sobre
  sus pacientes y sus hallazgos, secretaria solo ve, admin sin acceso.
- Seed: tratamientos ficticios y usuarios demo `odontologo` y `secretaria`
  (hoy no hay forma de crearlos y sin ellos la feature no se puede usar).
- Frontend `features/odontograma`: grilla FDI, caras, historial por pieza, aviso
  de alergias permanente; entrada desde la agenda. Usa `design-system/tokens.css`.
- Sin PHI en logs (backend y frontend). Datos 100% ficticios.

**Fuera de alcance**: dentición temporal (51–85), periodontograma, imágenes,
firma digital, presupuestos (C-09), ABM de tratamientos y de usuarios (C-12),
evolución como nota de texto libre (ver D-14).

## Capabilities

### New Capabilities

- `clinica-odontograma-hc`: historia clínica por paciente con alergias siempre
  visibles, odontograma FDI con catálogo cerrado versionado e historial por pieza,
  catálogo de tratamientos de solo lectura, control de acceso clínico por rol y
  vínculo paciente-profesional, baja lógica y ausencia de PHI en logs.

### Modified Capabilities

- Ninguna. `core-models-identidad-pacientes`, `auth-rbac` y `agenda-turnos-core` se
  reutilizan sin cambiar requisitos: el seed crece de forma aditiva y la agenda
  suma un acceso al odontograma, igual que hizo C-07 con sus llamadas aditivas.

## Impact

- **Archivos nuevos**: `backend/app/modelos/{historia_clinica,hallazgo_odontograma,tratamiento}.py`,
  `backend/alembic/versions/005_clinica.py`,
  `backend/app/esquemas/clinica.py`,
  `backend/app/repos/{historia_repo,hallazgo_repo,tratamiento_repo}.py`,
  `backend/app/servicios/clinica_servicio.py`,
  `backend/app/api/{historias,odontograma,tratamientos}.py`,
  `frontend/src/features/odontograma/*`, `frontend/src/styles/odontograma.css`,
  tests `test_c08_*`.
- **Archivos extendidos**: `backend/app/main.py`, `backend/app/modelos/__init__.py`,
  `backend/app/db/seed.py`, `backend/app/repos/turno_repo.py` (método de vínculo),
  `frontend/src/App.tsx`, `frontend/src/main.tsx`,
  `frontend/src/features/agenda/{AgendaPage,TurnoCard}.tsx`.
- **Tests existentes que se rompen con la migración nueva y hay que ajustar**:
  `test_c07_migracion.py` (acepta solo `004_espera|005_espera` como cabeza),
  `test_c05_reserva_pg.py` (lista exacta de migraciones) y `db_utils.py` (la lista
  de tablas del reset debe sumar las cuatro nuevas).
- **Sin cambios**: stub `/clinica` (lo exige `test_routers.py`), `agenda_servicio`,
  EXCLUDE, contratos C-04..C-07.
- **Desbloquea**: C-09 (`HallazgoOdontograma` + `Tratamiento`).
- **Governance MEDIO**: propuesta solo de artefactos; las decisiones D-01..D-15
  quedan en `design.md` para revisión humana.

## Leer antes (fuente de verdad)

- `knowledge-base/04_modelo_de_datos.md` — §HistoriaClinica + HallazgoOdontograma, §Tratamiento / Presupuesto.
- `knowledge-base/05_reglas_de_negocio.md` — §RN-CL-01, §RN-CL-03, §RN-CL-04, §RN-GL-01, §RN-GL-02.
- `knowledge-base/06_funcionalidades.md` — §US-020, §US-021, §US-022.
- `knowledge-base/07_flujos_principales.md` — §Flujo 3.
- `knowledge-base/03_actores_y_roles.md` — matriz RBAC, fila Odontograma/HC.
- `CHANGES.md` — §[C-08], §[C-09].
- `design-system/README.md`, `design-system/tokens.css`, `design-system/components.html`.
