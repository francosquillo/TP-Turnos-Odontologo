# Design

## Context

El sistema cuenta con una SPA en React 18 + TypeScript + Vite que implementa toda la funcionalidad del consultorio odontológico. El repositorio ya posee una fundación de diseño aprobada en `design-system/` con `tokens.css` y `components.html`. Sin embargo, la navegación en `App.tsx` y las vistas públicas y de gestión utilizan HTML plano sin envoltorios estandarizados. Ver `proposal.md` para la motivación.

## Goals / Non-Goals

**Goals:**
- Unificar la experiencia visual de las 12 pantallas existentes bajo una misma dirección de arte clínica, sobria y profesional.
- Proveer un layout institucional reutilizable con header, branding y navegación adaptada al rol (`admin`, `odontologo`, `secretaria`, público).
- Aplicar retroalimentación táctil (`:active scale(0.97)`), foco accesible y transiciones rápidas en componentes interactivos.
- Mantener 100% verdes los 421 tests de Vitest existentes sin alterar `data-testid`, roles ni lógica de negocio.
- Verificar visualmente la adaptabilidad en viewports móvil (390×844) y escritorio (1440×900) con Playwright MCP.

**Non-Goals:**
- Modificar endpoints, servicios, modelos de datos o lógica del backend en Python.
- Agregar librerías de componentes externas o frameworks de utilidades CSS pesados (Tailwind, MUI, Chakra).
- Alterar flujos de negocio existentes (turnos, caja, liquidaciones, facturación o lista de espera).
- Re-diseñar el logotipo o la paleta de marca aprobada en `design-system/tokens.css`.

## Decisions

### D-01: CSS Modular puro basado en variables de tokens.css
- **Decisión**: Estilar componentes mediante clases CSS semánticas (`.topbar`, `.btn`, `.card`, `.field`, `.input`, `.badge`, `.table-wrap`) enlazadas directamente a las variables CSS de `frontend/src/styles/tokens.css`.
- **Alternativas consideradas**:
  - *Tailwind CSS*: Descartado para no agregar dependencias de compilación ni modificar la configuración de Vite del proyecto.
  - *CSS-in-JS (Styled Components / Emotion)*: Descartado por sobrecarga de render y complejidad innecesaria.
- **Razón**: Mantiene la arquitectura liviana, aprovecha el trabajo ya validado en `design-system/` y simplifica el mantenimiento.

### D-02: Componente AppHeader y Shell de navegación en shared/
- **Decisión**: Extraer la barra de navegación y estado de sesión de `App.tsx` hacia un componente modular `AppHeader` en `frontend/src/shared/layout/`, con contenedor responsivo `.wrap`.
- **Alternativas consideradas**:
  - *Mantener botones planos en App.tsx*: Descartado por falta de modularidad y pobre adaptabilidad en móviles.
- **Razón**: Permite encapsular el logo, el indicador de rol y las pestañas con `aria-current="page"` sin ensuciar el router principal.

### D-03: Ergonomía táctil y microinteracciones de Emil Kowalski
- **Decisión**: Incorporar feedback táctil en todos los botones y cards interactivas mediante `:active:not(:disabled) { transform: scale(0.97); }` y transiciones rápidas de 120ms (`--motion-fast`) con función `ease-out`.
- **Alternativas consideradas**:
  - *Animaciones complejas con Framer Motion*: Descartado para evitar latencia perceptiva en tareas repetitivas del personal de clínica.
- **Razón**: Brinda sensación inmediata de solidez y respuesta física en cada interacción.

### D-04: Verificación visual automatizada con Playwright MCP
- **Decisión**: Utilizar el servidor MCP de Playwright local para navegar la aplicación en `localhost:5173`, redimensionar a móvil (390×844) y escritorio (1440×900), y capturar screenshots de evidencia.
- **Alternativas consideradas**:
  - *Figma MCP o Browserbase*: Descartados por requerir cuentas externas, archivos en la nube o suscripciones pagas.
- **Razón**: Playwright MCP es 100% local, gratuito, determinístico y ya está instalado en el entorno.

### D-05: Invarianza estricta de selectores de prueba
- **Decisión**: Cualquier refactorización de JSX debe preservar intactos los atributos `data-testid`, nombres de campo `id`/`htmlFor`, textos de botones y roles ARIA.
- **Razón**: Garantiza que la suite de 421 tests de Vitest continúe pasando sin modificaciones de aserciones.

## Risks / Trade-offs

- **[Riesgo: Desajuste de estilos heredados entre features]** → Mitigación: Definir reglas de layout globales en `layout.css` y `components.css` que utilicen selectores específicos sin colisionar con los archivos CSS ya existentes de odontograma o caja.
- **[Riesgo: Romper tests de Testing Library por cambio de estructura DOM]** → Mitigación: Ejecutar `npm test` después de editar cada componente para detectar regresiones de inmediato.
- **[Riesgo: Desbordamiento en pantallas móviles]** → Mitigación: Diseñar las vistas públicas bajo enfoque móvil primero con `min-width: 0` y contenedores elásticos.
