# Visión y Objetivos

Fuente: `discovery/discovery.md` (2026-09-29) + stack definido por la facultad.

## Propósito del sistema

Sistema web de gestión de turnos odontológicos que cierra el circuito completo **turno → clínica → cobro con seguridad trazable** para consultorios argentinos: elimina el ausentismo con confirmación automática por WhatsApp, reemplaza la agenda en papel, digitaliza la historia clínica en odontograma FDI y liquida obras sociales por nomenclador sin planillas manuales.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| Paciente | Reservar y confirmar turnos sin llamar | Consultar historial, pagar tratamientos |
| Secretaria/recepcionista | Agenda siempre actualizada sin llamados manuales | Cobrar en caja, cierre diario |
| Odontólogo | Registrar y presupuestar en el sillón | Diagnosticar sobre odontograma |
| Administrador del sistema (incl. Dueño como alias — decisión 2026-10-05) | Controlar producción, ocupación y ausentismo; configurar roles, aranceles y exportaciones | Liquidar profesionales y OS, exportar reportes; mantener datos maestros |

## Alcance v1.0 (núcleo académico)

> **Prioridad de evaluación (decisión 2026-10-05): Turnos/Agenda.** La épica turnos/agenda (agenda, reserva, WhatsApp, lista de espera) es la prioritaria; el resto acompaña.

- Agenda multi-profesional con estados de turno + anti-solapamiento por sillón/box.
- Reserva de turnos online 24/7 sin llamadas.
- Recordatorios y confirmación por WhatsApp que actualizan la agenda.
- Odontograma digital (notación FDI) + historia clínica + presupuestos desde el odontograma.
- Cuenta corriente por paciente, caja con cierre diario y recibos.
- Liquidación de obras sociales por nomenclador con exportación CSV/PDF.
- Roles (odontólogo/secretaria/admin) + importación de pacientes por Excel/CSV.
- Diferenciadores v1.0: lista de espera con cierre de loop, validador OS pre-turno, reseñas Google post-turno, exportación total de datos, página de seguridad documentada, costo WhatsApp transparentado.

## Fuera de alcance

- Recepcionista virtual con IA 24/7 (etapa posterior: costo por volumen).
- Portal del paciente.
- Cobros con MercadoPago y facturación electrónica AFIP/ARCA (escalamiento).
- Periodontograma, imágenes/radiografías, firma digital con validez legal.
- Multi-sede, analytics/scorecards, API pública.
- App móvil nativa (alcanza web responsiva).

## Métricas de éxito

- Ausentismo reducido vs. línea base del consultorio (referencia mercado: −82% declarado por vendors ⚠️).
- % de turnos confirmados sin intervención manual.
- Tiempo de liquidación de OS por período (antes vs. después).
- Ocupación de sillón y tasa de aceptación de presupuestos.

## Restricción dura: plazo de entrega

Entrega del TP: **12 de Octubre 2026**. Equipo de 3 personas; ~7 días desde el 05/10/2026 (decisión 2026-10-05). El roadmap debe planificarse dentro de esa ventana.
