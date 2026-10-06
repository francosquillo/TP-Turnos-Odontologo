# Modelo de Datos

## Dominios

- **Identidad y acceso**: usuarios, roles, sesiones.
- **Agenda**: profesionales, sillones/boxes, turnos, lista de espera.
- **Pacientes**: datos filiatorios, cobertura OS.
- **Clínica**: historia clínica, odontograma, tratamientos, presupuestos.
- **Cobros**: cuenta corriente, movimientos, caja, recibos.
- **Obras sociales**: OS, planes, nomenclador, liquidaciones.
- **Notificaciones**: mensajes, plantillas, eventos.

## ERD

```
Usuario *──1 Rol (rol simple por FK: usuario.rol_id → rol.id; decisión IN-02 del 2026-10-05)
Profesional 1──* Turno *──1 Paciente
Sillon 1──* Turno (unique parcial anti-solapamiento)
Paciente 1──1 HistoriaClinica 1──* HallazgoOdontograma (pieza FDI + cara + estado)
Hallazgo *──* Tratamiento → Presupuesto 1──* ItemPresupuesto
Paciente 1──1 CuentaCorriente 1──* Movimiento
Caja 1──1 CierreDiario 1──* MovimientoCaja (+ Recibo)
ObraSocial 1──* Plan 1──* Arancel (nomenclador: código + precio + vigencia)
Liquidacion 1──* ItemLiquidacion (turno/prestación × arancel)
Turno 1──* Notificacion · Paciente 1──* EsperaEntry
```

## Entidades

### Usuario
- Atributos: id (uuid), nombre, email (unique), password_hash, rol_id (FK → Rol, un solo rol por usuario), activo, created_at.
- Relaciones: *—1 Rol (rol simple FK; sin tabla intermedia `usuario_rol` en v1.0 — decisión IN-02 del 2026-10-05). Roles fijos: `admin` (incl. alias Dueño, IN-01), `odontologo`, `secretaria`.
- Constraints: email único, >=1 admin activo (regla de resguardo).
- Índices: email.

### Paciente
- Atributos: id, nombre, apellido, dni (unique nullable), teléfono, email, obra_social_id + plan_id (nullable), notas, consentimiento_datos (bool + fecha).
- Relaciones: 1—1 HistoriaClinica, 1—1 CuentaCorriente, 1—* Turno, 1—* EsperaEntry.
- Índices: dni, apellido, teléfono.

### Profesional
- Atributos: id, usuario_id (FK nullable), matrícula, especialidades, agenda_config (duración slot, horario semanal JSON).
- Relaciones: 1—* Turno.

### Sillon (box/sillón)
- Atributos: id, nombre, sede (texto, v1.0 sede única — decisión 2026-10-05; dejar campo extensible a multi-sede post-TP), activo.
- Relaciones: 1—* Turno.

### Turno
- Atributos: id, paciente_id, profesional_id, sillon_id, inicio, fin, estado (pendiente|confirmado|asistido|ausente|cancelado), origen (secretaria|online|lista_espera), token_confirmacion (nullable, hash), sobre_turno (bool).
- Relaciones: 1—* Notificacion, 0—1 ItemLiquidacion.
- Constraints: **anti-solapamiento**: exclusion por (profesional|sillon, rango) — `EXCLUDE USING gist (profesional WITH =, tstzrange(inicio,fin) WITH &&)` ídem sillón; sobreturno solo con flag explícito + auditoría.
- Índices: (profesional, inicio), (sillon, inicio), estado, token hash.

### HistoriaClinica + HallazgoOdontograma
- HC: id, paciente_id (unique), antecedentes, alergias, updated_at.
- Hallazgo: id, hc_id, pieza_fdi (11–48), cara (oclusal/mesial/distal/vestibular/palatina/lingual/raíz), estado (sano/caries/obturación/corona/endodoncia/implante/ausente/etc.), fecha, profesional_id.
- Índices: (hc_id, pieza_fdi).

### Tratamiento / Presupuesto
- Tratamiento (catálogo): id, código interno, código_nomenclador (nullable), nombre, precio_base.
- Presupuesto: id, paciente_id, profesional_id, estado (borrador|presentado|aceptado|rechazado|cobrado), total, created_at. Items: presupuesto_id, tratamiento_id/hallazgo_id, cantidad, precio.
- Regla: el presupuesto nace de hallazgos del odontograma (RN-CL-01).

### CuentaCorriente / Movimiento
- CC: id, paciente_id (unique), saldo (derivado, no editable directo).
- Movimiento: id, cc_id, tipo (cargo|pago|ajuste), monto, concepto, turno_id/presupuesto_id/recibo_id (nullable), created_at.
- Constraints: monto != 0; anulación vía contramovimiento, nunca UPDATE/DELETE.

### Caja / CierreDiario / Recibo
- Caja: id, fecha (unique), abierta_por, estado (abierta|cerrada), total_sistema, total_contado, diferencia.
- MovimientoCaja: id, caja_id, medio (efectivo|transferencia|tarjeta — MP solo futuro), monto, recibo_id.
- Recibo: id, número (secuencia), paciente_id, monto, medio, anulado (bool + motivo).
- Constraints: cierre diario obligatorio; egresos/anulaciones con motivo trazado.

### ObraSocial / Plan / Arancel / Liquidacion
- OS: id, nombre, activa. Plan: id, os_id, nombre.
- Arancel: id, plan_id, código_nomenclador, descripción, precio, vigencia_desde/hasta.
- Liquidación: id, os_id, período (mes), estado (borrador|presentada|cobrada), total. Items: prestación (turno_id/tratamiento), arancel aplicado, monto.
- Exportación: CSV + PDF presentable.

### Notificacion
- Atributos: id, canal (whatsapp|email|sms), plantilla, destinatario_ref, turno_id, estado (encolada|enviada|entregada|leída|fallida), costo (nullable — transparencia Meta USD 0,026/ref), payload (sin datos clínicos).
- Constraints: **nunca** texto clínico en el cuerpo (solo recordatorio/turno).

### EsperaEntry (lista de espera)
- Atributos: id, paciente_id, profesional_id/especialidad, preferencia_horaria, estado (activa|ofrecida|convertida|vencida), created_at.
- Flujo: hueco libre → ofrece al primero → reserva o avisa al siguiente (cierre de loop).

## Seed data inicial

- Roles (admin —incl. alias Dueño—/odontólogo/secretaria) + 1 admin inicial.
- 1 sillón demo + 1 profesional demo con agenda semanal (sede única v1.0).
- Nomenclador de prueba con OS ficticia ("OS Ficticia Demo" + planes/aranceles de ejemplo — decisión 2026-10-05).
- Plantillas WhatsApp: recordatorio 48/24 h, confirmación, hueco liberado, reseña Google.
