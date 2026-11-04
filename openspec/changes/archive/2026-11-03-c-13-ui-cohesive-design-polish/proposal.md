# Proposal

## Why

El frontend del sistema odontológico fue construido progresivamente a lo largo de 12 changes funcionales priorizando la lógica de negocio y contratos REST. Como resultado, las pantallas públicas y de gestión utilizan HTML básico sin estilar o estilos CSS fragmentados, sin un layout global uniforme, sin navegación armónica y con inconsistencias visuales. Esta propuesta implementa un rediseño cohesivo, accesible (WCAG AA) y táctil sobre todas las 12 vistas ya implementadas, reutilizando estrictamente el sistema de tokens existente (`tokens.css`) sin modificar endpoints de backend ni alterar la suite de tests de Vitest.

## What Changes

- **Layout institucional unificado**: Creación de `AppHeader` con logo provisional del consultorio, insignia del rol del usuario autenticado, botón de cierre de sesión y navegación responsiva basada en pestañas con estado activo (`aria-current="page"`).
- **Estilización de vistas públicas (Paciente)**:
  - `Inicio`: Landing page con bienvenida profesional, llamado a la acción destacado y tarjeta de seguridad.
  - `Reservas`: Flujo de reserva organizado en pasos visuales, píldoras de horario con estados interactivos y formulario accesible.
  - `Confirmar` y `OfertaEspera`: Tarjetas centrales tipo voucher con estado claro, contador regresivo y botones táctiles.
  - `Seguridad`: Grid de compromisos de privacidad y políticas de datos honestas con tipografía jerárquica.
- **Estilización de vistas operativas (Staff)**:
  - `Login`: Tarjeta centrada con campos de entrada estilizados y alertas de error accesibles.
  - `AgendaPage`: Cards de turnos enriquecidas con borde de estado (`--estado-*`), badges semánticos, filtros compactos y modal de cancelación refinado.
  - `OdontogramaPage`: Grilla dental FDI 11–48 limpia, alertas de alergias visibles y panel de presupuestos integrado.
  - `CuentaPage` y `CajaPage`: Métricas de saldo y balance diario destacadas en cards superiores, tablas de movimientos uniformes y modales claros.
  - `LiquidacionesPage` y `ListaEsperaPage`: Tablas densas con espaciado consistente, estados semánticos y botones de descarga/acción.
  - `PanelAdmin`: Organización en sub-pestañas visuales para usuarios, importación masiva y exportación total.
- **Microinteracciones y accesibilidad**: Adopción de feedback táctil (`:active scale(0.97)`), foco por teclado visible (`outline: var(--focus-ring)`), y curvas de transición fluidas respetando `prefers-reduced-motion`.

## Capabilities

### New Capabilities
- `ui-cohesive-shell`: Capa de presentación visual unificada, layout global responsivo y componentes estéticos basados en tokens para pacientes y personal de la clínica.

### Modified Capabilities
*(Ninguna. Los requerimientos funcionales y reglas de negocio del backend y del sistema se conservan intactos).*

## Impact

- **Código afectado**: Exclusivamente archivos frontend en `frontend/src/` (`App.tsx`, `shared/`, `pages/`, `features/`, `styles/`).
- **APIs y Backend**: Cero impacto. No se tocan endpoints FastAPI, esquemas Pydantic, modelos SQLAlchemy ni migraciones.
- **Dependencias**: Cero paquetes npm adicionales. Se utiliza CSS nativo tokenizado enlazado a `tokens.css`.
- **Tests**: Conservación estricta de todos los atributos `data-testid`, roles y etiquetas evaluadas por los 421 tests de Vitest.
