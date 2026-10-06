# Funcionalidades

Épicas del MVP doble pista (núcleo académico + diferenciadores). Post-TP explícitamente excluido (ver `01`, Fuera de alcance).

> **Decisiones 2026-10-05**: épica prioritaria para la evaluación = **Turnos/Agenda (Épicas A+B)**. AFIP/facturación electrónica = post-TP (escalamiento, fuera de v1.0). Pagos = **simulados** (sin integración real con MercadoPago en v1.0). Nomenclador de prueba con **OS ficticia** ("OS Ficticia Demo"). Sede única en v1.0. Donde diga "dueño" léase Admin (alias, IN-01).

## Épica A: Agenda y reserva ⭐ PRIORITARIA (decisión 2026-10-05 — lo que más pondera la evaluación)

### US-001 — Agenda multi-profesional con estados
**Como** secretaria **Quiero** ver la agenda diaria/semanal por profesional y sillón con estados de color **Para** operar el día sin papel.
**Criterios**: - [ ] CA-1 vistas día/semana/mes. - [ ] CA-2 estados pendiente/confirmado/asistido/ausente/cancelado. - [ ] CA-3 choque imposible (RN-TU-01).
**Reglas**: RN-TU-01, RN-TU-02, RN-TU-03.

### US-002 — Reserva online 24/7
**Como** paciente **Quiero** reservar eligiendo profesional, día y hora **Para** no depender del horario de secretaría.
**Criterios**: - [ ] CA-1 solo huecos válidos (RN-TU-05). - [ ] CA-2 genera turno `pendiente` + token. - [ ] CA-3 importa/crea paciente mínimo.
**Reglas**: RN-TU-03, RN-TU-04, RN-TU-05.

### US-003 — Reprogramar/cancelar
**Como** secretaria **Quiero** arrastrar o cancelar un turno con motivo **Para** mantener la agenda real.
**Criterios**: - [ ] CA-1 reprogramar revalida solapamiento. - [ ] CA-2 cancelación pide motivo.
**Reglas**: RN-TU-01, RN-TU-03.

## Épica B: Comunicación WhatsApp

### US-010 — Recordatorios automáticos
**Como** sistema **Quiero** enviar recordatorios 48/24 h por cola Redis **Para** bajar ausentismo sin trabajo manual.
**Criterios**: - [ ] CA-1 encolado async con reintentos. - [ ] CA-2 registra estado + costo. - [ ] CA-3 sin datos clínicos en el texto.
**Reglas**: RN-NO-01, RN-NO-02, RN-NO-04.

### US-011 — Confirmación en 1 clic
**Como** paciente **Quiero** confirmar con un link **Para** no llamar ni instalar nada.
**Criterios**: - [ ] CA-1 token un solo uso que actualiza la agenda. - [ ] CA-2 token expirado muestra alternativa de contacto.
**Reglas**: RN-TU-03, RN-TU-04.

### US-012 — Lista de espera con cierre de loop ⭐ diferenciador
**Como** paciente en espera **Quiero** que me avisen si se libera un hueco **Para** adelantar mi turno.
**Criterios**: - [ ] CA-1 oferta al primero con expiración de 2 h (decisión 2026-10-05). - [ ] CA-2 cascada al siguiente si expira/rechaza. - [ ] CA-3 conversión crea turno `confirmado`.
**Reglas**: RN-TU-06.

## Épica C: Clínica

### US-020 — Odontograma FDI
**Como** odontólogo **Quiero** cargar hallazgos por pieza/cara **Para** tener la boca del paciente digitalizada.
**Criterios**: - [ ] CA-1 piezas 11–48 + caras + catálogo de estados. - [ ] CA-2 historial por pieza.
**Reglas**: RN-CL-03, RN-CL-04.

### US-021 — Historia clínica
**Como** odontólogo **Quiero** antecedentes, alergias y evolución **Para** atender con contexto.
**Criterios**: - [ ] CA-1 alergias visibles siempre. - [ ] CA-2 soft-delete.
**Reglas**: RN-GL-01, RN-GL-03.

### US-022 — Presupuesto desde odontograma
**Como** odontólogo **Quiero** generar el presupuesto desde los hallazgos en el sillón **Para** cerrar el plan con el paciente.
**Criterios**: - [ ] CA-1 ítems referencian hallazgo. - [ ] CA-2 estados hasta aceptado/cobrado o rechazado.
**Reglas**: RN-CL-01, RN-CL-02.

## Épica D: Cobros y caja

### US-030 — Cuenta corriente por paciente
**Como** secretaria **Quiero** ver deuda, cargos y pagos **Para** cobrar sin planilla.
**Criterios**: - [ ] CA-1 saldo derivado. - [ ] CA-2 cargos desde presupuestos aceptados.
**Reglas**: RN-CO-02, RN-CO-03.

### US-031 — Caja con cierre diario
**Como** secretaria **Quiero** cobrar con recibo y cerrar la caja del día **Para** rendir sin errores.
**Criterios**: - [ ] CA-1 recibo secuencial. - [ ] CA-2 cierre con diferencia declarada. - [ ] CA-3 bloqueo del día siguiente sin cierre. - [ ] CA-4 medios simulados (efectivo/transferencia/tarjeta simulada; sin integración real MP en v1.0 — decisión 2026-10-05).
**Reglas**: RN-CO-01, RN-CO-04.

## Épica E: Obras sociales

Datos de prueba con OS ficticia ("OS Ficticia Demo" — decisión 2026-10-05). AFIP/facturación electrónica = post-TP, fuera de v1.0.

### US-040 — Validador pre-turno ⭐ diferenciador
**Como** secretaria **Quiero** ver la cobertura del tratamiento para el plan del paciente antes del turno **Para** evitar sorpresas de cobro.
**Criterios**: - [ ] CA-1 muestra %/monto cubierto vs. a cargo. - [ ] CA-2 usa arancel vigente.
**Reglas**: RN-OS-01, RN-OS-03.

### US-041 — Liquidación por nomenclador
**Como** admin (dueño como alias) **Quiero** liquidar por período y exportar CSV/PDF **Para** presentar reintegros sin planillas.
**Criterios**: - [ ] CA-1 agrupa por OS/plan/período. - [ ] CA-2 exportación presentable.
**Reglas**: RN-OS-02, RN-OS-03.

## Épica F: Administración

### US-050 — Roles y usuarios
**Como** admin **Quiero** gestionar usuarios y roles **Para** que cada uno vea lo suyo.
**Criterios**: - [ ] CA-1 matriz de `03`. - [ ] CA-2 resguardo último admin.
**Reglas**: RN-AU-03, RN-GL-02.

### US-051 — Importación Excel + exportación total ⭐
**Como** admin **Quiero** importar pacientes y exportar todo **Para** migrar y evitar lock-in.
**Criterios**: - [ ] CA-1 importación con reporte de errores por fila. - [ ] CA-2 exportación total descargable.
**Reglas**: RN-GL-01.

### US-052 — Página de seguridad ⭐ diferenciador
**Como** admin (dueño como alias) **Quiero** una página pública de seguridad (cifrado, respaldos, auditoría) **Para** diferenciarme donde ningún local evidencia nada.
**Criterios**: - [ ] CA-1 contenido honesto y verificable. - [ ] CA-2 pública sin login.
