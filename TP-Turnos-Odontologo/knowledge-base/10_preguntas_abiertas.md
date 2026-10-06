# Preguntas Abiertas

Origen: `discovery/discovery.md` §11. Resueltas desde entonces: stack (facultad lo fijó) y equipo (3 personas).
Actualización 2026-10-05: las 11 decisiones del equipo dejan este archivo sin preguntas pendientes. Se conserva cada pregunta original visible junto a su resolución.

## Inconsistencias detectadas — RESUELTAS 2026-10-05

### IN-01 — Dueño: ¿rol propio o alias de Admin? ✅ RESUELTA 2026-10-05
**Decían `03`/`05`**: matriz con columna "(Dueño = Admin o rol propio*)"; RN-AU-03 exigía >= 1 admin sin distinguir dueño.
**Decisión (vinculante)**: **Dueño = Admin (mismo rol, alias)**. Sin rol Dueño separado.
**Propagada a**: `03` (actor y matriz unificados en Admin), `04` (roles fijos con alias), `05` (RN-AU-03 aclara alias), `01` (objetivos), `06` (US-041/US-052 "Como admin"), `07` (Flujo 5), `08` (RBAC).

### IN-02 — Rol simple (FK) vs. N—M usuario_rol ✅ RESUELTA 2026-10-05
**Decía `04`**: a decidir en Sprint 1.
**Decisión (vinculante)**: **Rol simple por FK** (un rol por usuario: `usuario.rol_id` → `rol.id`; sin tabla intermedia `usuario_rol` en v1.0).
**Propagada a**: `04` (ERD + entidad Usuario), `03` (nota de 3 roles fijos).

## Preguntas abiertas (todas RESUELTAS 2026-10-05)

| Prioridad original | Pregunta original | Decisión 2026-10-05 | Reflejada en |
|---|---|---|---|
| Alta | ¿Hay consultorio piloto real para validar? | **NO. Datos 100% ficticios y de prueba obligatorio. Modelo, arquitectura y roadmap preparados para futura producción real.** | 02, 08, 09 (SU-01/SU-00), 10 |
| Alta | ¿Qué OS se usa para el nomenclador de prueba? | **OS ficticia** ("OS Ficticia Demo" + ejemplos). | 04 (seed), 05 (nota RN-OS), 06 (Épica E), 09 (SU-02/SU-04) |
| Alta | ¿Qué pondera más la evaluación: clínica, turnos o administración? | **Turnos.** Épica turnos/agenda (A+B) prioritaria. | 01 (alcance), 06 (nota + Épica A ⭐) |
| Media | ¿AFIP entra en el TP o queda en escalamiento? | **Escalamiento** (fuera de v1.0). | 06 (nota Épica E), 01 (ya estaba fuera de alcance) |
| Media | ¿Pagos reales (sandbox MP) o simulados? | **Simulados.** Sin integración real MP en v1.0. | 06 (US-031 CA-4), 07 (Flujo 4), 08 (nota seguridad) |
| Media | ¿Dónde se despliega y con qué política las HC de prueba? | **Localmente (Docker Compose local).** Datos ficticios; sin cloud en v1.0. | 08 (seguridad + despliegue), 02 |
| Media | Plazo de entrega del TP (hitos) | **12 de Octubre 2026.** Restricción dura; equipo 3, ~7 días desde el 05/10. | 01 (sección plazo), 10 |
| Baja | ¿Sede única alcanza en v1.0? | **Sí, sede única.** Sin multi-sede en v1.0; extensible. | 04 (Sillon.sede), 06, 01 (fuera de alcance), 09 (SU-03) |
| Baja | Ventana de expiración de oferta de lista de espera (2 h propuesto) | **Sí, 2 horas** (confirmado). | 05 (RN-TU-06), 07 (Flujo 6), 06 (US-012) |

[DISCOVERY] Todos los campos `kb.discovery` se resolvieron con confianza alta (problema/usuarios/reglas en discovery + stack de facultad); no hay entradas de baja confianza.
