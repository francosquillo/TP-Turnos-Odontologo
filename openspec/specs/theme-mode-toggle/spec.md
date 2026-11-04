# theme-mode-toggle Specification

## Purpose
Provee la alternancia accesible entre tema claro y tema oscuro con persistencia local y sincronización inmediata con las variables del sistema de diseño.

## Requirements

### Requirement: Dark theme token definitions
El sistema de diseño SHALL proveer un conjunto de tokens de color oscuros bajo el selector `[data-theme="dark"]` que redefina fondos, superficies, bordes y textos sin romper los contrastes de legibilidad WCAG AA.

#### Scenario: Dark theme attribute applied
- **WHEN** el atributo `data-theme="dark"` está presente en el elemento raíz `<html>`
- **THEN** las variables CSS `--color-bg`, `--color-surface`, `--color-border` y `--color-text` adoptan valores oscuros con contraste adecuado

### Requirement: Theme toggle button in header
El componente `AppHeader` SHALL incluir un control interactivo accesible para alternar entre el tema claro y el tema oscuro.

#### Scenario: User clicks theme toggle
- **WHEN** el usuario hace clic en el botón de alternancia de tema en el encabezado
- **THEN** el tema cambia inmediatamente de claro a oscuro (o viceversa) y el estado se almacena en `localStorage`

### Requirement: Theme persistence and initial detection
El sistema SHALL inicializar el tema basándose en la preferencia previamente guardada en `localStorage` o, en su defecto, en la preferencia del sistema operativo (`prefers-color-scheme`).

#### Scenario: Initial page load with saved preference
- **WHEN** la aplicación se carga en el navegador y existe un valor guardado en `localStorage`
- **THEN** el sistema aplica inmediatamente el tema guardado en el elemento raíz `<html>`
