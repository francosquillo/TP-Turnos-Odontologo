# Open Dental (Open Dental Software, EE.UU., https://www.opendental.com/)

> Fecha de consulta de todas las fuentes: 2026-09-29. Convención: ✅ comprobado en fuente oficial/documentación · ⚠️ afirmación comercial o de marketplace sin verificación independiente · ❌ No evidenciado en las fuentes públicas consultadas.

## 1. Nombre, empresa, país, URL oficial
- **Producto:** Open Dental. **Empresa:** Open Dental Software. **País:** Estados Unidos (Oregón, tel. 503). **URL:** https://www.opendental.com/ ✅.

## 2. Segmento
- ✅ Consultorios de cualquier tamaño, multilocation/enterprise con descuentos por volumen, unidades móviles (cada una factura como sede), escuelas de odontología/higiene **gratis**, integraciones médicas/institucionales por FTE provider.

## 3. Modalidad (cloud / on-premise / móvil / IA)
- ✅ Self-hosted/on-premise (Windows + MySQL/MariaDB, el consultorio administra servidor, backups y seguridad) + **Open Dental Cloud** (hospedado por el vendor, solo EE.UU., en lanzamiento limitado con cupo).
- ✅ Apps móviles: **ODTouch** (tablet/operativo clínico) y **ODMobile** (incluye mensajería 2-way).
- ✅ IA vía integración: **Pearl AI** (desde v24.3) y transcripción OCR en eServices Bundle.

## 4. Agenda
- ✅ Appointment Module por **operatorias** (sillones/profesionales); **ASAP List** documentada con 4 vías de marcado (cita programada, planificada, no programada, recall) y pestañas de citas/recalls no programados.
- ✅ **Web Sched ASAP**: ante un hueco, clic derecho → Text ASAP List → envío escalonado de SMS/email con link único para aceptar/rechazar; crea un blockout informativo y registra historial; cadencia según cercanía (cada 1 min si <2 h … cada 8 min si >48 h).
- ✅ Reglas anti-doble-reserva configurables ("Prevent double booking" + Appointment Rules por procedimiento) y patrones de tiempo por tipo de recall.
- ❌ Vistas diaria/semanal y bloqueos por tipo/motivo en detalle visual: el módulo existe pero su UX no fue verificada con capturas en esta investigación.

## 5. Turnos digitales
- ✅ **Web Sched** (eServices): agenda online con disponibilidad real según horarios de proveedores y operatorias; **Web Sched Recall** con recordatorios automáticos email/SMS y links familiares agregados; confirmaciones/avisos automáticos (eConfirmations/eReminders); **Patient Portal** (citas, planes, imágenes, WebMail); **Payment Portal** (pagos online, desde v25.4 con tap/Apple Pay/Google Pay vía Global Payments).
- ❌ Cancelación y reprogramación self-service por el paciente: No evidenciado en la documentación consultada.

## 6. Automatización
- ✅ Recalls automatizados con intervalos, tope de envíos y estados; ASAP; mensajes masivos configurables.
- ❌ Campañas de marketing y gestión de reseñas: No evidenciado (el foco es operativo, no growth).

## 7. Gestión clínica
- ✅ Graphical Tooth Chart, perio chart, imágenes (carpeta OpenDentImages A–Z), planes de tratamiento, notas clínicas, seguimiento de laboratorio, prescripción electrónica (DoseSpot/Ensora eRx), integración Pearl AI para Rx.

## 8. Administración
- ✅ Billing/statements, claims electrónicos, ERA con asignación a lab fees, fee schedules y guías arancelarias (incl. Canadá 2026), verificación electrónica, **queries personalizables** (built-in/graphic/user queries), reportes, portal de pagos.
- ✅ Precios de eServices publicados (ver §12): vitrina de costos poco común en el sector.

## 9. Integraciones
- ✅ **API de Open Dental** comprobada indirectamente: el Cloud admite integraciones que usan la API y restringe las "Unauthorized Integrations" que no la usan; puentes documentados (Global Payments, Clerri, Pearl).
- ❌ VoIP, marketing y pasarelas adicionales en detalle: No evidenciado.

## 10. Operación
- ✅ Multi-location/enterprise, replicación (soporte pago por hora), perfiles de seguridad por usuario/grupo, **audit trail** (el manual lo cita para controlar accesos de contratistas), Middle Tier HTTPS para acceso remoto, soporte teléfono/chat/email incluido en la suscripción.
- ❌ Exportación masiva/migración de salida y su costo: No evidenciado.

## 11. Seguridad
- ✅ Modelo documentado con honestidad técnica: **HIPAA es responsabilidad del consultorio**; el software es una herramienta de ayuda (guía de setup, análisis de riesgos, BAAs con terceros).
- ✅ Cifrado tabulado oficialmente: eConnector AES-192, TLS 1.2/1.3 en portales, BitLocker/EFS/MariaDB at-rest recomendados, backups Cloud cifrados y off-site con prueba nocturna de integridad, BAA firmable, MFA en Cloud.
- ⚠️ Advertencia oficial: SMS y email plano **NO son seguros** (no enviar PHI) — límite honesto a copiar como criterio de diseño.
- ❌ SOC 2 / ISO 27001 del vendor: No evidenciado (no declarado públicamente).

## 12. Modelo comercial
- ✅ Precios públicos en https://www.opendental.com/site/fees.html: self-hosted **USD 199/mes/sede** (12 meses, luego reducida **USD 149**; +USD 20/proveedor extra más de 3); otros países **USD 89**; **Cloud USD 430/mes/sede** (1 proveedor, 15 sesiones, 50 GB) + USD 150/proveedor extra; **eServices Bundle USD 165/mes/sede** (texting, recordatorios, Web Sched, eClipboard); SMS saliente USD 0.04 (EE.UU.); ODTouch USD 85/mes; ODMobile USD 75/mes; eRx USD 29–57/prov/mes; descuentos por volumen y prepago.
- ❌ Trial público autofirable: No evidenciado.

## 13. Fortalezas / limitaciones / diferenciales
- **Fortalezas:** funcionalidad profunda y precios 100 % públicos; automatización de huecos (ASAP escalonado) de referencia; customización extrema (queries, definiciones, recalls); costo real ~15–19 % menor que 2003 ajustado por inflación (transparencia inusual).
- **Limitaciones:** UX datada Windows; self-hosted exige IT propio (servidor, backups, seguridad HIPAA a cargo del cliente); Cloud solo EE.UU. y limitado; funciones paciente fragmentadas en eServices pagos; SMS sin PHI (límite para flujos clínicos por mensaje).
- **Diferencial:** el único que publica ingeniería de seguridad y precios con este detalle; su ASAP escalonado es el mejor modelo de waitlist verificable del relevamiento.

## 14. Adopción
- ✅ Capterra 4.6/5 (87–88 reseñas); G2 4.3/5 (43–47 reseñas); agregado Toolradar 4.4/5 (202 reseñas). Versión estable 25.4 (04/2026), beta 26.2 (08/2026): desarrollo activo comprobado.
- ❌ Cuota de mercado publicada/auditada: No evidenciado.

## Qué copiar para AR
- **Copiar/adaptar:** ASAP List + envío escalonado por cercanía del hueco (ideal para ausentismo AR); prevención de doble reserva configurable por prestación; recordatorios con links familiares agregados; queries/reportes personalizables para el odontólogo-dueño; tabla pública de cifrado por canal (qué va por WhatsApp y qué no); pricing transparente publicado.
- **No aplica en AR:** claims/ERA/fee schedules de seguros EE.UU.; eRx DoseSpot/Ensora; Cloud solo EE.UU.; licenciamiento por proveedor.
- **Ojo crítico:** el modelo self-hosted traslada seguridad y backups al cliente — en AR conviene SaaS gerenciado. Y la regla "SMS sin PHI" debe traducirse a "WhatsApp sin datos sensibles + canal seguro para clínicos/imágenes".

## Fuentes (consultadas 2026-09-29)
- https://www.opendental.com/ (home, versiones 25.4/26.x)
- https://www.opendental.com/site/fees.html (precios self-hosted, Cloud, eServices, eRx, descuentos)
- https://www.opendental.com/site/opendentalcloud.html (Cloud solo EE.UU., backups cifrados, BAA)
- https://www.opendental.com/site/hipaa.html (HIPAA a cargo del consultorio)
- https://www.opendental.com/site/encryption.html (tabla de cifrado por canal, AES/TLS, advertencia SMS/PHI)
- https://www.opendental.com/site/eservices.html y https://www.opendental.com/site/websched.html (eServices, Web Sched Recall/ASAP)
- https://opendental.com/manual/webschedasap.html y https://www.opendental.com/Manual/asaplist.html (ASAP List, cadencia de envíos)
- https://opendental.com/manual/webschedrecallsetup.html y https://opendental.com/manual/recallsetup.html (recalls automáticos)
- https://www.opendental.com/site/textintegrated.html (Integrated Texting)
- https://www.opendental.com/site/version25_4.html (Payment Portal, Global Payments, tap/Apple Pay)
- https://www.capterra.ca/software/122350/open-dental (4.6/5, 87 reseñas), https://toolradar.com/tools/open-dental (agregado 4.4/202), G2 Open Dental Software (4.3/5, 43 reseñas)

## Puntajes sugeridos
- (a) Turnos y automatización: **4** — ASAP escalonado + Web Sched + recalls configurables, todo documentado; UX datada y sin cancelación self-service evidenciada.
- (b) Clínica odontológica: **5** — chart + perio + eRx + imágenes + Pearl AI; el más completo del relevamiento.
- (c) Integraciones/WhatsApp: **3** — API comprobada y texting 2-way; SMS oficialmente no apto para PHI; WhatsApp nulo en EE.UU.
- (d) Administración/cobros: **5** — billing + claims + ERA + queries + pagos tap; todo con precio público.
- (e) Experiencia del paciente: **3** — portal + pago online + recordatorios, pero fragmentado en módulos pagos y sin app paciente insignia.
- (f) Seguridad/exportación: **3** — cifrado tabulado + BAA + backups Cloud; SOC 2 no declarado y HIPAA a cargo del cliente.
- (g) Precio/adopción: **5** — precio público más bajo y transparente; Capterra 4.6 con ~88 reseñas; sin cuota publicada.
