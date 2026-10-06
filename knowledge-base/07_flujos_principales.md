# Flujos Principales

## Flujo 1: Reserva online + confirmación
**Disparador**: paciente entra a `/reservas`. **Actor**: paciente (no autenticado).
1. Frontend pide disponibilidad (profesional + rango fechas).
2. API calcula huecos (horario profesional − turnos existentes, RN-TU-05).
3. Paciente elige, deja nombre/teléfono (crea o matchea paciente mínimo).
4. API crea turno `pendiente` + token, encola WhatsApp de confirmación.
5. Paciente toca el link → `GET /confirmar/:token` → turno `confirmado`, agenda actualizada.
**Casos de error**: hueco tomado en concurrente → 409 + re-oferta; token expirado → pantalla con teléfono del consultorio.

## Flujo 2: Recordatorios automáticos (async)
**Disparador**: cron cada hora. **Actor**: worker Redis.
1. Worker busca turnos `pendiente|confirmado` a 48/24 h.
2. Encola mensaje por turno (idempotente por `turno_id + tipo`).
3. Envío vía WhatsApp API; registra estado + costo; si falla → fallback email/SMS.
4. Respuesta del paciente (webhook firmado) → actualiza estado del turno.
**Casos de error**: sin número válido → marca `fallida` + avisa a secretaría; webhook sin firma → 401 + log.

## Flujo 3: Atención en sillón (odontograma → presupuesto → cobro)
**Disparador**: turno `confirmado` → `asistido`. **Actor**: odontólogo.
1. Marca asistencia; abre odontograma del paciente.
2. Carga hallazgos (pieza/cara/estado) → guarda en HC.
3. Genera presupuesto desde hallazgos (RN-CL-01), lo presenta, paciente acepta/rechaza.
4. Aceptado → cargos a cuenta corriente; secretaria cobra (Flujo 4).
**Casos de error**: presupuesto rechazado → motivo + queda en historial para recupero.

## Flujo 4: Cobro y cierre de caja
**Disparador**: fin de atención o pago espontáneo. **Actor**: secretaria.
1. Desde cuenta corriente genera cobro (medio simulado: efectivo/transferencia/tarjeta simulada — sin integración real MP en v1.0, decisión 2026-10-05) → recibo secuencial.
2. Movimiento en CC + movimiento de caja del día.
3. Al cierre: sistema compara total vs. declarado; registra diferencia; cierra día (RN-CO-01 bloquea operar sin cierre).
**Casos de error**: diferencia ≠ 0 → exige declararla; anular recibo → contramovimiento + motivo.

## Flujo 5: Liquidación de obra social
**Disparador**: fin de mes. **Actor**: admin (dueño como alias).
1. Elige OS + período → sistema lista prestaciones × arancel vigente (RN-OS-03).
2. Revisa, marca estado `presentada`, exporta CSV/PDF.
3. Al cobrar: `cobrada` + registra en caja como ingreso.
**Casos de error**: prestación sin arancel vigente → fila marcada para revisión manual.

## Flujo 6: Lista de espera con cierre de loop
**Disparador**: cancelación libera hueco. **Actor**: sistema.
1. Busca primera espera compatible activa → envía oferta con expiración de 2 h (decisión 2026-10-05, RN-TU-06).
2. Acepta → turno `confirmado`; rechaza/expira → siguiente en cascada.
**Casos de error**: nadie acepta → hueco queda libre en agenda pública.

## Flujo 7: Auth y sesiones
**Disparador**: login. **Actor**: staff.
1. `POST /auth/login` (email + password) → access JWT corto + refresh rotativo en cookie httpOnly.
2. Frontend adjunta Bearer; API valida + chequea RBAC (`03`).
3. Refresh rota; logout invalida.
**Casos de error**: credenciales inválidas → 401 genérico (sin enumerar usuarios); token expirado → 401 + refresh silencioso.
