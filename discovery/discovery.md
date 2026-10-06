# Discovery — Sistema de gestión de turnos odontológicos

**Fecha**: 2026-09-29
**Fuentes investigadas**: 21 sistemas fichados (ver `discovery/sources/`): 16 odontológicos puros + 5 de contexto (4 generalistas + 1 capa sobre PMS)

**Convención de evidencia**: ✅ comprobado en fuente oficial · ⚠️ afirmación comercial del proveedor sin verificación independiente · ❌ no evidenciado en las fuentes públicas consultadas.

## 1. Problema que resuelve

Los consultorios odontológicos argentinos pierden turnos e ingresos por
ausentismo sin confirmación automática, gestionan la agenda en papel o
planillas que dependen de una sola persona, extravían historias clínicas,
liquidan obras sociales a mano con errores y nunca recuperan a los pacientes
inactivos. Los sistemas locales cubren fragmentos del problema, pero ninguno
cierra el circuito completo turno → clínica → cobro con seguridad trazable:
o bien cobran en dólares con inteligencia artificial cara (Órbita), o bien
tienen la funcionalidad pero sin evidencia de seguridad (DentalSoft AR), o
bien les falta la automatización de turnos por completo (DentiClick).

## 2. Usuarios / roles

- **Paciente**: reserva un turno online sin llamar, confirma o cancela por
  WhatsApp, consulta su historial y paga su tratamiento.
- **Secretaria/recepcionista**: agenda, reprograma y confirma turnos, cobra en
  caja y hace el cierre diario.
- **Odontólogo**: registra la historia clínica en el odontograma, diagnostica,
  presupuesta y presenta el plan de tratamiento en el sillón.
- **Dueño/director de clínica**: controla producción, ocupación y ausentismo,
  liquida profesionales y obras sociales, exporta reportes.
- **Administrador del sistema**: configura roles y permisos, aranceles por obra
  social y exportaciones de datos.

## 3. Casos de uso

1. Como paciente, quiero reservar un turno online las 24 horas para no
   depender del horario de la secretaría.
2. Como secretaria, quiero que la confirmación por WhatsApp actualice sola la
   agenda para no tener que llamar paciente por paciente.
3. Como odontólogo, quiero registrar los hallazgos en el odontograma y generar
   el presupuesto en el momento para cerrar el plan de tratamiento con el
   paciente en el sillón.
4. Como dueña de la clínica, quiero liquidar las obras sociales por nomenclador
   para presentar los reintegros sin planillas ni errores de cálculo.
5. Como paciente en lista de espera, quiero que me avisen si se libera un hueco
   para adelantar mi turno.

## 4. Competidores / soluciones existentes

| Competidor | Problema que resuelve | Pricing | Diferenciadores |
|---|---|---|---|
| Órbita (AR) | Gestión + recepcionista IA por WhatsApp con agenda por sillón | Chat USD 200/mes; Gestión USD 25–113/mes; sin trial | Anti-solapamiento por sillón, Juez IA de urgencias, obras sociales AR |
| DentalSoft AR (AR) | Suite local completa con reserva online y MercadoPago | Gratis $0; $30k/$50k/$75k ARS por profesional | Anti-solapamiento, sync Google Calendar, liquidaciones OS, demo instantánea |
| DentiClick (AR) | Odontología con obras sociales a precio bajo | USD 0/12/22/35 por consultorio; 1 mes gratis | Liquidación OS por nomenclador CSV/PDF, demo pública de odontograma |
| Dentalink (CL) | Plataforma regional con localización fiscal por país | Cotización por país | RIPS/FE Colombia, Verifactu España, +20 países |
| Simples Dental (BR) | Suite brasileña con cobros locales integrales | BRL 137–321/mes; trial 7 días | Pix/boleto/cuenta digital/NFS-e, firma con validez jurídica |
| DaleControl (MX) | Clínica con imagen 3D e IA a precio accesible | MXN $419/$689/mes, sin permanencia | CBCT 3D en navegador, caja con PIN, WhatsApp sin sobrecosto |
| Open Dental (EE.UU.) | PMS profundo con precios 100 % públicos | USD 199→149/sede; Cloud 430 | ASAP escalonado anti-huecos, tabla de cifrado honesta, queries custom |
| CareStack (EE.UU.) | All-in-one con revenue cycle completo | USD 829/1.299/mes | Membership/auto-debit/pay-by-text, triple marco HIPAA+SOC 2+ISO 27001 |

**Notas**: los competidores directos para el TP son los argentinos (Órbita,
DentalSoft AR, DentiClick, Dentaly). Los regionales LatAm (Dentalink,
DentiDesk, Dentality, Simples, Historia, DaleControl) aportan localización
fiscal y WhatsApp como referencia. Los estadounidenses/británicos
(CareStack, Open Dental, Dentrix Ascend, Curve, Tab32, Dentally) son
aspiracionales en funcionalidad y seguridad, con lógicas de seguros
intransferibles. Los generalistas (AgendaPro, Doctoralia, Fresha,
Feegow) y la capa NexHealth sirven solo de referencia de UX de
captación — por decisión del usuario no entran en la comparativa principal.

## 5. Funcionalidades necesarias

- Agenda multi-profesional con estados de turno y anti-solapamiento por
  sillón/box.
- Reserva de turnos online 24/7 sin llamadas.
- Recordatorios y confirmación por WhatsApp que actualizan la agenda sin
  intervención manual.
- Odontograma digital (notación FDI) con historia clínica y presupuestos
  generados desde el odontograma.
- Cuenta corriente por paciente, caja con cierre diario y recibos.
- Liquidación de obras sociales por nomenclador con exportación CSV/PDF.
- Roles (odontólogo/secretaria/admin) e importación de pacientes por Excel/CSV.

## 6. Funcionalidades opcionales

- Recepcionista virtual con IA 24/7 por WhatsApp (a diferencia del núcleo,
  requiere costo por volumen de mensajes — se deja para una etapa posterior).
- Portal del paciente con historial, turnos y documentos.
- Cobros con MercadoPago y facturación electrónica AFIP/ARCA (a diferencia de
  DentiClick, que no los tiene — son el camino de escalamiento, no del TP).
- Periodontograma, imágenes/radiografías y firma digital con validez legal.
- Multi-sede, analytics con scorecards por profesional y API pública.
- App móvil nativa (a diferencia de Simples Dental, no es necesaria para la
  v1 — el acceso web responsivo alcanza).

## 7. Reglas de negocio

- Un sillón/profesional no admite turnos superpuestos (choque imposible,
  con detección explícita en sobreturnos).
- Todo turno tiene un estado (pendiente/confirmado/asistido/ausente/cancelado)
  y la confirmación del paciente lo actualiza sin intervención.
- El presupuesto nace del odontograma y se sigue hasta su aceptación o cobro.
- La cobertura de obra social se aplica por tratamiento y plan antes del cobro,
  y se liquida por período con informe presentable.
- El cierre de caja diario es obligatorio, con trazabilidad de egresos y
  anulaciones.
- Ningún dato clínico sensible viaja por WhatsApp/SMS plano (criterio tomado
  de Open Dental: canal seguro para lo clínico, mensajería solo para
  turnos/recordatorios).

## 8. Integraciones

- WhatsApp (Business API/Meta) para recordatorios, confirmaciones y reserva
  asistida — con el costo por mensaje transparentado en el modelo (criterio
  tomado de DentalSoft AR: USD 0,026 de Meta por recordatorio).
- Google Calendar (sincronización por profesional) y Google (reserva +
  solicitud automática de reseñas post-turno).
- MercadoPago para cobros y AFIP/ARCA para facturación electrónica (etapa de
  escalamiento, no del núcleo académico).
- Email/SMS como fallback de notificaciones y Excel/CSV para
  importación/exportación (a diferencia de Tab32, no se necesita un data
  warehouse en la v1 — alcanza con PDF/Excel).

## 9. Restricciones

- Es un TP universitario (UTN) que puede escalar a producto real: el MVP debe
  tener un núcleo de alcance académico evaluable más un camino de
  escalamiento explícito.
- Sin stack, plazo ni equipo fijos por ahora (decisión del usuario: estos
  puntos van a preguntas abiertas, no son restricciones).
- Si el sistema escala a producto con datos reales, aplica la normativa
  argentina de datos de salud (Leyes 25.326/26.529) — ningún competidor local
  la evidencia hoy, lo que es una oportunidad de diferenciación.

## 10. Riesgos

- **Supuesto sin probar**: que los pacientes confirmen por WhatsApp en vez de
  ignorar los mensajes — si hay fatiga de mensajes o el costo Meta por volumen
  se dispara, la automatización deja de ser rentable (mitiga: transparentar el
  costo, email gratuito, cupos por plan).
- **Supuesto sin probar**: que las obras sociales acepten la liquidación
  digital del sistema — cada prestadora exige su formato (mitiga: empezar con
  CSV/PDF por nomenclador y agregar el validador pre-turno después).
- **Riesgo**: si el consultorio no puede migrar sus datos del sistema anterior,
  la adopción se frena por lock-in (mitiga: importación por Excel y demo
  precargada, como DentiClick y DentalSoft AR).
- **Riesgo**: dependencia total de WhatsApp/Meta para un canal crítico
  (baneos, cambios de precio) — se mitiga con fallback SMS/email y la regla de
  no enviar datos clínicos sensibles por mensajería.
- **Riesgo**: el alcance supere la capacidad de un equipo estudiantil (mitiga:
  núcleo académico primero; IA, pagos y fiscal van en etapas posteriores).

## 11. Preguntas abiertas

- ¿Stack tecnológico del TP?
- ¿Plazo de entrega y tamaño del equipo?
- ¿Hay un consultorio piloto real para validar con usuarios?
- ¿La facturación AFIP entra en el alcance del TP o queda para el
  escalamiento?
- ¿Pagos reales (sandbox de MercadoPago) o simulados?
- ¿Qué obra social se usa para el nomenclador de prueba?
- ¿Dónde se despliega y con qué política se manejan historias clínicas de
  prueba?
- ¿Qué pondera más la evaluación UTN: clínica, turnos o administración?

---

## Anexo A — Tabla comparativa (16 sistemas odontológicos puros, por relevancia para Argentina)

| # | Sistema (país) | Segmento | Modalidad | Agenda | Turnos digitales | Clínica | Admin / cobros | Integraciones | Precio |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Órbita** (AR) | Consultorio→red (+3 sedes); expansión médica | SaaS + WhatsApp IA + voz (próx.) | ✅ Por sillón con anti-solapamiento; agendamiento anti-huecos; controles auto | ✅ Chat IA 24/7, confirma 48/24 h, Juez IA urgencias (⚠️ 806 turnos/30 d.) | ✅ Odontograma + periodontograma + voz + lab + trazabilidad lotes | ✅ Caja, convenios/liquidaciones OS, embudo presupuestos; ❌ MP/AFIP | ✅ WhatsApp IA + Dentalink/Bilog/Benty; ❌ API/MP/AFIP | ⚠️ USD: Chat 200/mes; Gestión 25–113/mes; sin trial |
| 2 | **DentalSoft AR** (AR) | Consultorio/clínica (1–4+ prof.) | SaaS + IA WhatsApp/web | ✅ Semanal/diaria/mensual, drag&drop, sobreturnos con anti-solapamiento, bloqueos, multi-sede, sync Google Calendar | ✅ Reserva online 4 pasos 24/7, recepcionista IA 24 h, portal paciente, web propia | ✅ Odontograma 18 estados FDI + historial, ortodoncia, planes, consentimientos, recetas; ❌ periodontograma | ✅ Caja multi-método con MercadoPago, liquidaciones OS/profesionales PDF, KPI; ❌ AFIP | ✅ WhatsApp + GCal + MP + PDF/Excel; ❌ API/AFIP | ✅ ARS: Gratis $0; $30k/$50k/$75k por prof.; demo instantánea |
| 3 | **DentiClick** (AR) | Individual / con secretaria / clínica | SaaS + PWA + IA asistente | ✅ Diaria/semanal/mensual, estados, multi-prof., reserva 24/7 mini-web; ❌ sillón/bloqueos | ✅ Mini-web con subdominio + IA; ❌ confirmación auto WhatsApp, lista espera | ✅ Odontograma por caras/pieza (demo pública), historia, presupuestos, imágenes, visor 3D; ❌ periodontograma/firma | ✅ Cta. cte., liquidación OS por nomenclador CSV/PDF, insumos; ❌ MP/AFIP/online | ❌ Ninguna declarada (producto cerrado) | ✅ USD 0/12/22/35 por consultorio; 1 mes gratis |
| 4 | **Dentaly** (AR) | Individual / clínica / multisede | SaaS multi-dispositivo | ⚠️ Semanal/diaria, por profesional, dashboard (evidencia débil, sitio JS) | ⚠️ Recordatorios WhatsApp declarados; ❌ reserva online evidenciada | ⚠️ Odontograma + periodontograma + consentimientos declarados; sin demo | ⚠️ Finanzas, inventario, OS declarados; sin detalle cobros/fiscal | ⚠️ WhatsApp/OS declarados; ❌ MP/AFIP/API | ✅ ARS: Pro $35k; Clínica $100k; Multisede cotización |
| 5 | **Dentalink** (CL) | Independiente / multicentro / IPS / cadena | SaaS 100 % web | ✅ Central, reagendación paciente, multicentro; ❌ sillón/bloqueos/anti-solap. | ✅ Online 24/7, confirma/reagenda, telemedicina; ⚠️ Contact Center IA (marketing) | ✅ Odontograma + periodontograma + orto + firma + imágenes; ⚠️ IA Rx/voz (marketing) | ✅ Pagos, presupuestos, comisiones, inventario; fiscal por país (SII/RIPS/Verifactu); ❌ AFIP AR | ✅ WhatsApp/email, telemedicina, pagos; ❌ API/calendarios | ⚠️ Cotización por país; sin trial autoadministrado |
| 6 | **DentiDesk** (CL) | Clínicas, multisucursal, sindicatos, universidades | SaaS web | ✅ Personalizable, estados configurables, convenios; ❌ sillón/bloqueos | ⚠️ "Agendamiento online" como integración; ❌ autogestión documentada | ✅ Anamnesis, fichas especialidad, triple nomenclatura, presupuestos; ❌ perio/imágenes | ✅ Facturación SII Chile, Alegra DO, stock, 20+ reportes; ❌ caja detallada | ✅ SII/Alegra; ⚠️ WhatsApp en preparación (2025, no operativo); ❌ API | ⚠️ Cotización (CLP); demo 15 días |
| 7 | **Simples Dental** (BR) | Independiente / clínica (Basic/Plus/Pro) | SaaS + apps 4.8–4.9★ + Alexa | ✅ Online, link agendamiento, confirma auto WhatsApp/SMS, control por sillones, bloqueos, multiagenda | ✅ Reserva 24/7, Copiloto en WhatsApp Web, términos/cobros por WhatsApp; ⚠️ Secretaria IA (lanzamiento) | ✅ Prontuario, odontograma→presupuestos, anamnesis, imágenes ilimitadas, firma jurídica, recetario; ❌ perio | ✅ Pix/boleto/cuenta digital/NFS-e, comisiones, morosidad, score crédito; 100 % BR | ✅ WhatsApp + Alexa + maquininha; ❌ API/calendarios | ✅ BRL 137–321/mes; trial 7 días; ⚠️ +19k clínicas, 9.6 Reclame Aqui |
| 8 | **Historia Dental** (CO) | Independiente / clínica pequeña (hasta 5 doctores) | SaaS web | ✅ Multi-doctor, reasignación; ❌ vistas, recordatorios, sillones (módulo más débil) | ❌ Sin reserva online ni WhatsApp funcional | ✅ Odontograma + CIE-10 automático, RIPS JSON, consentimientos firmados, OrthoAnalyzer, +70 plantillas | ⚠️ Presupuestos, ctas. paciente; ❌ caja/facturación emisora | ❌ Ninguna funcional (solo RIPS normativo) | ✅ COP: Gratis 1 año; $25k–$110k/mes (~USD 9–35); más barato |
| 9 | **Dentality** (MX) | Independiente / clínica / grupo multisedes | SaaS web + app móvil | ✅ Por doctor/sillón/sucursal, estados en vivo, saldos en cita | ⚠️ Cancelación por paciente (captura); confirma vía WhatsApp; ❌ reserva pública/portal | ✅ Expediente + odontograma + planes por fases + recetas firmadas por WhatsApp; ❌ perio/imágenes | ✅ Caja, saldos, CFDI, presupuestos, inventario, reportes | ✅ WhatsApp + CFDI; ❌ API/calendarios/pagos online | ⚠️ Cotización (MXN); trial 14 días sin tarjeta |
| 10 | **DaleControl** (MX) | Clínica nueva / profesional / grande | SaaS navegador + IA | ✅ Inteligente multi-doctor/sede, recordatorios WhatsApp incluidos sin sobrecosto; reglas finas ❌ | ✅ Bot agenda 24/7, portal paciente, recetas digitales; ❌ link web/lista espera | ✅ Odontograma + periodontograma + voz + CBCT 3D nube + IA Rx + STL en navegador | ✅ Caja con PIN, corte diario, CFDI 4.0 automático, reportes | ✅ WhatsApp + CFDI; ❌ API/calendarios | ✅ MXN $419/$689/mes, sin permanencia, 1er mes $19/$29 |
| 11 | **Tab32** (EE.UU.) | Chico 1–3 prov. (Alpine) / DSO (Summit) | Cloud GCP + IA pay-per-use | ✅ Drag&drop, alertas (alergias), multi-sede; reglas finas ❌ | ✅ Self-scheduling, eClipboard, portal (engagement = add-on) | ✅ Odontograma + perio por voz + imagen nativa + PiAI/Pearl + orto end-to-end | ✅ Claims/ERA/elegibilidad + pagos + data warehouse BigQuery | ✅ API integral (2023); ❌ catálogo público; sin WhatsApp | ✅ USD 125 (año 1) / 225 / Summit custom; trial 14 días |
| 12 | **Open Dental** (EE.UU.) | Cualquier tamaño, multilocation, escuelas gratis | On-premise + Cloud (solo EE.UU.) + apps | ✅ Por operatorias, ASAP List 4 vías, Web Sched ASAP escalonado, anti-doble-reserva configurable | ✅ Web Sched real, recalls auto, portales paciente/pagos (tap/Apple Pay); ❌ cancela self-service | ✅ Chart + perio + eRx + imágenes + Pearl AI; más completo | ✅ Billing + claims + ERA + queries custom + pagos; todo con precio público | ✅ API + texting 2-way; ⚠️ SMS no apto PHI | ✅ USD 199→149/sede (otros países 89); Cloud 430; eServices 165; ⚠️ Capterra 4.6 (88) |
| 13 | **Dentrix Ascend** (EE.UU.) | Individual / multilocation / DSO / móvil | Cloud 100 % + IA (add-on) | ✅ Smart scheduling multi-sede centralizado; reglas finas ❌ | ✅ Booking 24/7 nativo + Google, forms pre-visita, 2-way messaging | ✅ Charting + Detect AI VideaHealth (FDA) + voz + imagen nativa | ✅ Elegibilidad instantánea, claims/ERA, pagos, analytics | ❌ Ecosistema cerrado, sin API pública | ⚠️ Contact sales; ⚠️ 35k prácticas; Capterra 4.1 (235) |
| 14 | **Curve Dental** (EE.UU.) | Startup / independiente / multi-sede / DSO | Cloud AWS + IA | ✅ Multi-prov./sede "your schedule your way"; reglas finas ❌ | ✅ Self-scheduling 24/7 + GRO (recordatorios/campañas/acciones); ❌ cancela self-service | ✅ Charting + perio voz + imagen nube + IA; planes visuales | ✅ eClaims/ERA/elegibilidad + Business Analytics | ✅ API (permisos documentados); ❌ catálogo/VoIP | ⚠️ Sin precio público; Capterra 4.4 (285, mayor muestra) |
| 15 | **CareStack** (EE.UU.) | Startup / individual / multilocation / DSO + NHS UK | Cloud Azure + IA (plan Intelligence) | ✅ Multi-specialty, vistas custom, Short Call List + Appointment Finder, huddle board | ✅ Online scheduling, portal, kiosco, 2-way SMS, consentimientos digitales | ✅ Tx + perio por voz + imagen FDA nativa + Overjet + firma + lab + orto/perio/cirugía | ✅ RCM completo + membership/auto-debit/pay-by-text + scorecards proveedor | ✅ Terceros sin cargo; API no detallada | ✅ USD 829/1.299/mes; ⚠️ Capterra 4.8 (217) |
| 16 | **Dentally** (UK) | Single/multi-site, NHS/privado/mixto | Browser puro (Chrome, hasta 4G) + IA | ✅ Por proveedor + short-notice filler ≤5 días + booking integrado | ✅ Portal (booking/forms/historia/kiosco) + smart recalls por template+canal | ✅ Charting configurable + perio comparativa + Vision AI; ⚠️ críticas mixtas charting | ✅ NHS/UDA/claims 4 naciones + reportes chair-time; pagos vía Stripe/Worldpay | ✅ API + marketplace; sin VoIP | ⚠️ GBP £125–£510 (inconsistencia entre páginas); Capterra 3.6 (18) |

*Excluidos de esta tabla por decisión del usuario (sistemas generalistas o no-PMS, usables solo como contexto/UX): AgendaPro, Doctoralia, Fresha, Feegow Clinic y NexHealth.*

## Anexo B — Matriz ponderada y ranking

Pesos: turnos y automatización 25% · clínica 20% · integraciones locales/WhatsApp 15% · administración/cobros/facturación 15% · experiencia del paciente 10% · seguridad/exportación/trazabilidad 10% · precio/adopción 5%.

| Sistema | (a) Turnos 25% | (b) Clínica 20% | (c) Integ. 15% | (d) Admin 15% | (e) Paciente 10% | (f) Segur. 10% | (g) Precio 5% | **Ponderado** | Ranking |
|---|---|---|---|---|---|---|---|---|---|
| CareStack | 5 → 1.25 | 5 → 1.00 | 3 → 0.45 | 5 → 0.75 | 5 → 0.50 | 5 → 0.50 | 3 → 0.15 | **4.60** | 1.º |
| Órbita | 5 → 1.25 | 5 → 1.00 | 4 → 0.60 | 4 → 0.60 | 4 → 0.40 | 3 → 0.30 | 3 → 0.15 | **4.30** | 2.º |
| DentalSoft AR | 5 → 1.25 | 4 → 0.80 | 4 → 0.60 | 4 → 0.60 | 5 → 0.50 | 2 → 0.20 | 5 → 0.25 | **4.20** | 3.º (desempate AR) |
| DaleControl | 5 → 1.25 | 5 → 1.00 | 3 → 0.45 | 4 → 0.60 | 4 → 0.40 | 3 → 0.30 | 4 → 0.20 | **4.20** | 4.º (empate técnico) |
| Simples Dental | 5 → 1.25 | 4 → 0.80 | 3 → 0.45 | 5 → 0.75 | 4 → 0.40 | 2 → 0.20 | 4 → 0.20 | **4.05** | 5.º (empate técnico) |
| Open Dental | 4 → 1.00 | 5 → 1.00 | 3 → 0.45 | 5 → 0.75 | 3 → 0.30 | 3 → 0.30 | 5 → 0.25 | **4.05** | 6.º (empate técnico) |
| Tab32 | 4 → 1.00 | 4 → 0.80 | 3 → 0.45 | 4 → 0.60 | 4 → 0.40 | 4 → 0.40 | 3 → 0.15 | **3.80** | 7.º |
| Dentrix Ascend | 4 → 1.00 | 4 → 0.80 | 2 → 0.30 | 4 → 0.60 | 4 → 0.40 | 4 → 0.40 | 3 → 0.15 | **3.65** | 8.º (empate técnico) |
| Curve Dental | 4 → 1.00 | 4 → 0.80 | 2 → 0.30 | 4 → 0.60 | 5 → 0.50 | 3 → 0.30 | 3 → 0.15 | **3.65** | 9.º (empate técnico) |
| Dentalink | 4 → 1.00 | 4 → 0.80 | 3 → 0.45 | 4 → 0.60 | 4 → 0.40 | 2 → 0.20 | 3 → 0.15 | **3.60** | 10.º |
| Dentally | 4 → 1.00 | 3 → 0.60 | 2 → 0.30 | 3 → 0.45 | 4 → 0.40 | 4 → 0.40 | 3 → 0.15 | **3.30** | 11.º |
| Dentality | 4 → 1.00 | 3 → 0.60 | 3 → 0.45 | 4 → 0.60 | 3 → 0.30 | 1 → 0.10 | 3 → 0.15 | **3.20** | 12.º |
| DentiDesk | 3 → 0.75 | 4 → 0.80 | 2 → 0.30 | 3 → 0.45 | 3 → 0.30 | 2 → 0.20 | 3 → 0.15 | **2.95** | 13.º |
| DentiClick | 2 → 0.50 | 4 → 0.80 | 2 → 0.30 | 3 → 0.45 | 3 → 0.30 | 2 → 0.20 | 4 → 0.20 | **2.75** | 14.º |
| Historia Dental | 2 → 0.50 | 4 → 0.80 | 1 → 0.15 | 2 → 0.30 | 2 → 0.20 | 2 → 0.20 | 4 → 0.20 | **2.35** | 15.º |
| Dentaly | 2 → 0.50 | 3 → 0.60 | 2 → 0.30 | 2 → 0.30 | 2 → 0.20 | 1 → 0.10 | 3 → 0.15 | **2.15** | 16.º |

**Lectura**: el top ponderado lo lidera EE.UU. (funcionalidad), pero el top por
relevancia argentina es Órbita → DentalSoft AR → DentiClick. Los pesos elegidos
(turnos+clínica = 45%) premian el núcleo del TP; con otros pesos (p. ej. precio
20%) DentiClick e Historia Dental subirían y CareStack caería por sus USD 829+.

## Anexo C — Análisis competitivo

**Estándares de mercado** (lo que todo sistema serio ya tiene): agenda
multi-profesional con vistas diaria/semanal; reserva online 24/7;
recordatorios automáticos; odontograma digital; presupuestos y cuenta
corriente; reportes de gestión; SaaS en la nube sin instalación. Quien no
cubra esto está fuera del mercado.

**Diferenciales reales** (verificados, no marketing): anti-solapamiento por
sillón + agendamiento anti-huecos (Órbita); sobreturnos con detección de
solapamiento + sync Google Calendar (DentalSoft AR); liquidación de obras
sociales por nomenclador con CSV/PDF (DentiClick); demo pública interactiva
del odontograma (DentiClick) y demo instantánea precargada (DentalSoft AR);
WhatsApp incluido sin sobrecosto (DaleControl) frente al cobro por volumen
(AgendaPro, Simples); CBCT 3D en navegador + caja con PIN (DaleControl);
waitlist con cierre de loop —reserva al primero y avisa al resto— (NexHealth,
Open Dental ASAP escalonado); verificación de cobertura antes del turno
(Dentrix Eligibility, Dentally UDA); data warehouse/API abierta anti-lock-in
(Tab32); seguridad documentada con honestidad técnica incluyendo límites
(Open Dental "SMS sin PHI", Dentally "ISO 27001: No"); facturación fiscal
nativa por país (SII, CFDI, RIPS, NFS-e, TISS).

**Vacíos del mercado argentino**: (1) ningún competidor local combina
MercadoPago + facturación AFIP/ARCA + obras sociales en un solo flujo;
(2) seguridad trazable: ningún local publica cifrado, respaldos, auditoría ni
adecuación a Leyes 25.326/26.529 — todos puntúan 1–3 en seguridad;
(3) la confirmación por WhatsApp que actualiza la agenda existe solo
parcialmente (DentalSoft AR) y la reserva con IA es cara (Órbita Chat
USD 200/mes); (4) la lista de espera con cierre de loop no existe en ningún
local; (5) la exportación total de datos solo la declara Órbita;
(6) en pricing: o USD alto (Órbita), o evidencia funcional débil (Dentaly),
o automatización ausente (DentiClick).

**Oportunidades de innovación**: waitlist con cierre de loop por WhatsApp;
validador de obra social pre-turno (homólogo argentino de Eligibility/UDA);
confirmación en 1 clic que actualiza la agenda; solicitud automática de
reseñas Google post-turno; scorecards por profesional
(producción/aceptación/ausentismo); IA pay-per-use en vez de plan premium
(modelo Tab32/DaleControl por tokens); capa de acceso sobre sistemas legados
sin pedir migración (modelo NexHealth/Órbita Chat sobre Dentalink); pricing
que transparenta el costo Meta/WhatsApp; página de seguridad honesta como
argumento comercial.

## Anexo D — Recomendación: demos, UX y MVP

**5 competidores para demo** (mezcla argentina + mejor práctica): 1) DentalSoft
AR — espejo local directo, demo instantánea sin llamada; 2) Órbita — techo
local en WhatsApp IA + sillón (demo por llamada); 3) DentiClick — demo pública
de odontograma + obras sociales + plan gratis; 4) Open Dental — mejor
documentación funcional abierta (ASAP escalonado, tabla de cifrado), aunque
sin demo guiada; 5) DaleControl — CBCT 3D + caja con PIN + pricing
transparente (referente LatAm de imagen y cobros).

**3 referencias de UX** (generalistas y capa, permitidos aquí): 1) NexHealth —
booking (Google+QR+1-clic), waitlist con cierre de loop, recalls en 1 clic:
el modelo exacto de capa de acceso a copiar; 2) AgendaPro — marketplace,
Google Reserve, LinkPro y agentes IA (Sofía/Charly): el estándar regional de
captación y recordatorios; 3) Doctoralia — opiniones verificadas en 3 niveles
+ lista de espera inteligente + reserva con Google: el techo en reputación
y captación (a copiar sin su ecosistema cerrado ni su ausencia de WhatsApp).

**MVP sugerido — doble pista** (TP universitario escalable a producto):

- *Imprescindibles* (núcleo académico, demo evaluable): agenda
  multi-profesional con estados + anti-solapamiento por sillón/box; reserva
  online 24/7; recordatorios/confirmación por WhatsApp que actualizan la
  agenda; odontograma FDI + historia clínica + presupuestos; cuenta corriente
  + caja con cierre diario; liquidación de obras sociales por nomenclador
  (CSV/PDF); roles (odontólogo/secretaria/admin) + importación por Excel.
- *Diferenciadores* (separan del TP promedio y abren el camino a producto):
  lista de espera con cierre de loop; validador de obra social pre-turno;
  solicitud automática de reseñas Google; exportación total de datos; página
  de seguridad documentada (cifrado/respaldos/auditoría); costo WhatsApp
  transparentado en el modelo.
- *Etapas posteriores* (post-TP, escalamiento): recepcionista IA 24/7 por
  WhatsApp; portal del paciente; MercadoPago + facturación AFIP/ARCA;
  periodontograma + imágenes/Rx; multi-sede; analytics/scorecards; API
  pública; convenios con colegios odontológicos (modelo Doctocliq-COP: año
  gratis a matriculados jóvenes como motor de adopción).

## Supuestos asumidos al sintetizar

1. Los puntajes 0–5 de cada ficha (redactados por quien relevó) se tomaron
   como dato de entrada sin re-auditar sistema por sistema; solo se verificó
   a fondo lo nuevo (top-up: Tab32, DentalSoft AR, DaleControl).
2. ⚠️ equivale a afirmación comercial no verificada; la ausencia de evidencia
   pública se puntuó como carencia funcional (criterio conservador declarado
   en las fichas).
3. Los pesos de la matriz (25/20/15/15/10/10/5) priorizan el núcleo del TP
   (turnos+clínica = 45%); otro ponderador cambiaría el ranking.
4. Precios y tipos de cambio corresponden al 2026-09-29 y son volátiles
   (especialmente ARS/CLP/COP/MXN).
5. "Relevancia para Argentina" combina idioma, moneda/pagos locales, obras
   sociales, fiscalidad, WhatsApp y presencia local — no solo puntaje
   funcional.
6. Los homónimos "DentalSoft" (AR/CL/ES) son empresas distintas; la ficha
   nueva cubre solo la argentina (dentalsoft.com.ar).
7. Las métricas de proveedores (−82% ausencias, +22% reservas, etc.) se citan
   como afirmaciones, no como hechos.
8. El MVP supone equipo estudiantil sin plazo fijo: núcleo evaluable primero;
   integraciones costosas (IA, pagos, AFIP) después.

## Contradicciones entre fichas y cómo se resolvieron

1. **Dentally: £125 vs £265 base** — dos páginas oficiales dan cifras
   distintas; se consigna el rango £125–£510 con salvedad y se usa como
   ejemplo de lo que el TP no debe hacer (pricing único en moneda local).
2. **Dentalink: +15.000 clientes vs +65.000 profesionales/+7.000 clínicas** —
   cifras inconsistentes entre páginas del propio vendor; se consignan ambas
   con escepticismo explícito.
3. **Historia Dental: equivalencias USD subestimadas** — el sitio usa una tasa
   COP $3.150 desactualizada a 2026; se advierte y se prioriza el valor en COP.
4. **Historia Dental: testimonio negativo interno** — Carolina Betancourt
   (Medellín) declara ya no usarlo en el propio sitio del vendor; se consigna
   como señal de retención.
5. **DentalSoft homónimos** — Chile (on-premise v10, desde 2005) y España
   (pago único) frente a Argentina (SaaS): la ficha se acotó a `.com.ar`
   con advertencia de no mezclar evidencias.
6. **Tab32: USD 125 vs USD 225** — resuelto como tiers distintos (start-up
   año 1 vs establecida), no como contradicción.
7. **Open Dental: "Cloud solo EE.UU." vs "otros países USD 89"** — lo primero
   es Cloud gerenciado y lo segundo self-hosted internacional; conviven sin
   contradicción.
8. **Fresha: pricing vía Pabau (competidor)** — fuente interesada; se usa con
   cautela y solo como contexto/UX (no es puro de tabla A).
9. **NexHealth: sincronización "en segundos" vs "cada pocos minutos"** —
   inconsistencia menor del vendor; irrelevante para la tabla A (excluido por
   decisión del usuario), citada solo como referencia de UX.
