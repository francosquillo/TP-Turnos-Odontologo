# TP Turnos Odontólogo — Base de Conocimiento

Base generada en modo **ingest** desde `discovery/discovery.md` (2026-09-29) + stack definido por la facultad. Sin re-preguntar lo ya relevado.

## Índice de Archivos

| Archivo | Contenido |
|---|---|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance v1.0, fuera de alcance, métricas |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack, arquitectura general, integraciones, resumen API REST |
| [03_actores_y_roles.md](03_actores_y_roles.md) | 4 actores (Dueño = alias de Admin, 2026-10-05), matriz RBAC, rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | 7 dominios, ERD, 14 entidades, seed data |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | Reglas RN-TU/CL/CO/OS/AU/NO/GL |
| [06_funcionalidades.md](06_funcionalidades.md) | 6 épicas, 16 US con criterios y reglas |
| [07_flujos_principales.md](07_flujos_principales.md) | 7 flujos extremo a extremo |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, directorios, seguridad, env vars |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | 6 decisiones, 4 supuestos |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | 2 inconsistencias + 9 preguntas, todas RESUELTAS 2026-10-05 |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

Sistema web (FastAPI + React) que cierra turno → clínica → cobro para consultorios odontológicos argentinos: agenda anti-solapamiento con reserva online y confirmación por WhatsApp, odontograma FDI con presupuestos, caja con cierre diario y liquidación de obras sociales por nomenclador. Núcleo académico evaluable primero, 6 diferenciadores acotados, IA/pagos/fiscal en escalamiento post-TP.
