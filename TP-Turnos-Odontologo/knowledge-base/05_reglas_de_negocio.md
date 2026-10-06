# Reglas de Negocio

Código `RN-{DOMINIO}-{NN}` para trazabilidad. Origen: `discovery/discovery.md` §7.

## Dominio: Turnos (RN-TU)

- **RN-TU-01**: Un sillón/profesional no admite turnos superpuestos; el choque es imposible a nivel DB (constraint de exclusión).
- **RN-TU-02**: El sobreturno solo existe con flag explícito + motivo auditado.
- **RN-TU-03**: Todo turno tiene estado `pendiente|confirmado|asistido|ausente|cancelado`; la confirmación del paciente lo actualiza sin intervención.
- **RN-TU-04**: El token de confirmación es de un solo uso y expira (por defecto 72 h o al inicio del turno).
- **RN-TU-05**: La reserva online solo ofrece huecos dentro del horario del profesional y respeta RN-TU-01.
- **RN-TU-06**: Lista de espera: al liberarse un hueco se ofrece al primero con ventana de expiración de **2 horas** (decisión 2026-10-05); si rechaza/expira, pasa al siguiente (cierre de loop).

## Dominio: Clínica (RN-CL)

- **RN-CL-01**: El presupuesto nace del odontograma: cada ítem referencia un hallazgo (pieza FDI + tratamiento).
- **RN-CL-02**: El presupuesto se sigue hasta `aceptado|cobrado` o `rechazado` (con motivo).
- **RN-CL-03**: Notación FDI obligatoria (piezas 11–48) + cara; estados de un catálogo cerrado versionado.
- **RN-CL-04**: Ningún dato clínico sensible viaja por WhatsApp/SMS plano (criterio Open Dental).

## Dominio: Cobros (RN-CO)

- **RN-CO-01**: El cierre de caja diario es obligatorio antes de operar el día siguiente.
- **RN-CO-02**: Egresos y anulaciones exigen motivo y quedan trazados; las anulaciones generan contramovimiento.
- **RN-CO-03**: El saldo de cuenta corriente es derivado de movimientos; nunca se edita directo.
- **RN-CO-04**: Recibos con numeración secuencial sin huecos; anulado conserva número + motivo.

## Dominio: Obras sociales (RN-OS)

> Nota 2026-10-05: nomenclador de prueba con OS ficticia ("OS Ficticia Demo"). Datos 100% ficticios en v1.0.

- **RN-OS-01**: La cobertura se aplica por tratamiento y plan **antes** del cobro (validador pre-turno).
- **RN-OS-02**: La liquidación es por período + OS/plan, con informe presentable CSV/PDF.
- **RN-OS-03**: Aranceles versionados por vigencia; la liquidación usa el arancel vigente a la fecha de prestación.

## Dominio: Autenticación (RN-AU)

- **RN-AU-01**: JWT Bearer de corta vida + refresh rotativo; contraseña con hash Argon2/bcrypt.
- **RN-AU-02**: Paciente sin cuenta en v1.0: solo token público de un solo uso para confirmar/cancelar.
- **RN-AU-03**: Siempre debe existir >= 1 admin activo (bloquea desactivar/eliminar al último). Dueño = Admin (alias, IN-01 — decisión 2026-10-05), sin rol separado.
- **RN-AU-04**: Webhook WhatsApp verifica firma de Meta; rechaza payload no firmado.

## Dominio: Notificaciones (RN-NO)

- **RN-NO-01**: Recordatorios 48 h y 24 h antes; solo a turnos `pendiente|confirmado`.
- **RN-NO-02**: Cada mensaje registra estado y costo (transparencia costo Meta).
- **RN-NO-03**: Fallback email/SMS si WhatsApp falla o no hay número.
- **RN-NO-04**: Prohibido enviar datos clínicos en el cuerpo del mensaje.

## Excepciones globales

- **RN-GL-01**: Toda eliminación de datos clínicos/administrativos es lógica (soft-delete); el borrado físico solo vía exportación total + proceso admin.
- **RN-GL-02**: Auditoría mínima: quién/qué/cuándo en sobreturnos, anulaciones, cambios de arancel y accesos admin.
- **RN-GL-03**: Si escala a datos reales: Leyes 25.326/26.529 (consentimiento registrado, minimización de datos, cifrado en tránsito y reposo).
