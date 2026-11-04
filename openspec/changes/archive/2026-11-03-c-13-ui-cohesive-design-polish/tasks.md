# Tasks

## 1. Setup y Layout Shell (~2 h)

- [x] 1.1 Crear hojas de estilos base `frontend/src/styles/layout.css` y `components.css` con clases `.wrap`, `.topbar`, `.brand`, `.btn`, `.card`, `.field`, `.input` y `.table-wrap` consumiendo `tokens.css`. Verificar importación limpia en `main.tsx`. (~1 h)
- [x] 1.2 Implementar componente `AppHeader` en `frontend/src/shared/layout/` con logo provisional, indicador de sesión, insignia de rol y tabs con `aria-current="page"`. Integrar en `App.tsx` y verificar que los tests de `App.admin.test.tsx` sigan pasando. (~1 h)

## 2. Vistas públicas y autenticación (~2,5 h)

- [x] 2.1 Estilar `Inicio.tsx` con hero médico sobrio, tarjeta informativa y botones de acción rápida. Verificar renderizado en vitest y ausencia de errores de tipado. (~0,5 h)
- [x] 2.2 Estilar `Reservas.tsx` organizando el selector de fecha, las píldoras de horario con foco accesible y el formulario de contacto con validación visible. Verificar con `npm test -- Reservas.test.tsx`. (~1 h)
- [x] 2.3 Estilar `Confirmar.tsx`, `OfertaEspera.tsx` (tarjetas centrales de voucher con countdown) y `Login.tsx` (tarjeta de acceso con foco accesible). Verificar con vitest en sus respectivos archivos de prueba. (~1 h)

## 3. Agenda y Odontograma (~2,5 h)

- [x] 3.1 Estilar `AgendaPage.tsx` y `TurnoCard.tsx` aplicando bordes de estado semánticos (`--estado-*`), badges de estado, cabecera de fecha compacta y modal de cancelación refinado. Verificar con `npm test -- AgendaPage.test.tsx TurnoCard.test.tsx`. (~1,5 h)
- [x] 3.2 Pulir márgenes, badges de hallazgos y panel de presupuestos en `OdontogramaPage.tsx`. Verificar con `npm test -- OdontogramaPage.test.tsx`. (~1 h)

## 4. Gestión administrativa y financiera (~2,5 h)

- [x] 4.1 Estilar `CuentaPage.tsx` y `CajaPage.tsx` con tarjetas de resumen métrico superior (saldo, totales), tablas de movimientos limpias y modales de cobro/cierre destacados. Verificar con `npm test -- CuentaPage.test.tsx CajaPage.test.tsx`. (~1,5 h)
- [x] 4.2 Estilar `LiquidacionesPage.tsx` y `ListaEsperaPage.tsx` con tablas uniformes, badges semánticos y botones de exportación CSV/PDF. Verificar con `npm test -- LiquidacionesPage.test.tsx ListaEsperaPage.test.tsx`. (~1 h)

## 5. Panel de administración y Cierre (~1,5 h)

- [x] 5.1 Reorganizar `PanelAdmin.tsx` con navegación por sub-tabs limpias para usuarios (`UsuariosPage`), importación masiva (`ImportarPacientes`) y exportación total (`ExportacionTotal`). Verificar con `npm test -- UsuariosPage.test.tsx ImportarPacientes.test.tsx ExportacionTotal.test.tsx`. (~1 h)
- [x] 5.2 Estilar la vista pública de `Seguridad.tsx` con grilla de compromisos y tipografía jerárquica. Verificar con `npm test -- Seguridad.test.tsx`. (~0,5 h)

## 6. Verificación integral y Capturas visuales (~1,5 h)

- [x] 6.1 Ejecutar la suite completa de pruebas unitarias y de componentes del frontend (`npm test` / Vitest) confirmando 430/430 tests en verde y `npm run build` (`tsc --noEmit`) sin advertencias. (~0,5 h)
- [x] 6.2 Utilizar Playwright MCP para capturar pantallas de evidencia en viewports móvil (390×844) y escritorio (1440×900) para las 12 vistas, archivándolas en `openspec/changes/c-13-ui-cohesive-design-polish/verify/`. (~1 h)

## Workflow follow-up

- Actualizar `CHANGES.md` marcando C-13 como completado tras la verificación.
- Archivar el change con `openspec archive c-13-ui-cohesive-design-polish`.
