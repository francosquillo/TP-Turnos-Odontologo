# Spec Delta

## Purpose

Provee el layout institucional unificado, navegación responsiva y patrones visuales consistentes basados en tokens para pacientes y personal clínico.

## ADDED Requirements

### Requirement: Layout institucional y barra de navegación
El sistema SHALL presentar un header institucional con logo provisional, identificación del usuario autenticado, indicador de rol y pestañas de navegación responsivas con estado activo mediante aria-current="page".

#### Scenario: Navegación de usuario no autenticado
- **WHEN** un paciente o visitante no autenticado accede a la aplicación
- **THEN** el sistema muestra el logo institucional y pestañas hacia Inicio, Reservas y Seguridad, ocultando vistas operativas del personal

#### Scenario: Navegación de usuario staff autenticado
- **WHEN** un odontólogo, secretaria o administrador inicia sesión
- **THEN** la barra muestra su email, rol activo, botón para cerrar sesión y las pestañas correspondientes a su perfil operativo

### Requirement: Estilización accesible de vistas públicas
El sistema SHALL renderizar las pantallas públicas (Inicio, Reservas, Confirmar, OfertaEspera y Seguridad) con jerarquía visual clara, botones con objetivo táctil de al menos 44px y contraste tipográfico WCAG AA.

#### Scenario: Navegación en dispositivo móvil
- **WHEN** un paciente navega la pantalla de Reservas en una resolución móvil de 390px de ancho
- **THEN** el formulario de datos y las opciones de horarios se muestran ordenadas verticalmente sin desbordamiento horizontal

#### Scenario: Visualización de voucher de confirmación
- **WHEN** un paciente accede a una confirmación de turno con token válido
- **THEN** la interfaz renderiza una tarjeta central destacada con el estado de la cita, teléfono del consultorio y feedback visual

### Requirement: Interfaz densa y táctil para el personal
El sistema SHALL renderizar las vistas operativas del staff (Agenda, Odontograma, Caja, Cuenta, Liquidaciones, Espera, Admin) con densidad equilibrada de datos, tarjetas enriquecidas y feedback táctil en acciones primarias.

#### Scenario: Pulsación de acciones en turno de agenda
- **WHEN** el usuario pulsa un botón de estado o tarjeta de turno
- **THEN** el elemento responde con feedback táctil inmediato mediante escala activa y refleja el color semántico de su estado

#### Scenario: Apertura de caja y balance diario
- **WHEN** el personal de administración o secretaría consulta la vista de caja diaria
- **THEN** los totales de sistema y contado se visualizan en tarjetas de balance destacadas con formato monetario consistente

### Requirement: Preservación de selectores y contratos de test
El sistema SHALL conservar todos los atributos data-testid, roles ARIA y textos evaluados por las pruebas automatizadas en los componentes rediseñados.

#### Scenario: Ejecución de la suite completa de pruebas
- **WHEN** se ejecuta el comando de pruebas unitarias y de componentes en el frontend
- **THEN** la totalidad de los 421 tests de Vitest se ejecutan exitosamente sin regresiones ni fallas
