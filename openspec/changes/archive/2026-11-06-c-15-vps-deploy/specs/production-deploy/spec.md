# Spec Delta — production-deploy

## Purpose

Permite publicar la demo del sistema en un VPS gestionado con Easypanel, como un único servicio
Compose con dominio propio y HTTPS gestionados por el panel, con servicios endurecidos, secretos
solo por entorno, migraciones en el deploy y un runbook reproducible de operación y respaldo,
sin alterar el entorno local de desarrollo y verify.

## ADDED Requirements

### Requirement: Compose de producción separado del de desarrollo

El sistema SHALL proveer un archivo compose de producción independiente que levante frontend,
api, worker, migración, base de datos y redis, desplegable como un único servicio Compose de
Easypanel. El `docker-compose.yml` de desarrollo SHALL seguir funcionando sin cambios.

#### Scenario: Servicios de producción presentes

- **WHEN** se lee el compose de producción
- **THEN** define los servicios `frontend`, `api`, `worker`, `migrate`, `db` y `redis`, con `db` en `postgres:16` y `redis` en `redis:7`

#### Scenario: Compose de desarrollo intacto

- **WHEN** se lee `docker-compose.yml` tras aplicar el change
- **THEN** conserva sus cuatro servicios, puertos parametrizados por env y los tests existentes de compose siguen pasando

### Requirement: Sin puertos publicados en el host

Ningún servicio del compose de producción SHALL publicar puertos en el host, para no chocar con
el proxy del panel ni con otras aplicaciones del mismo servidor. El tráfico público SHALL
entrar solo por los dominios configurados en el panel.

#### Scenario: Ningún servicio declara ports

- **WHEN** se inspecciona el compose de producción
- **THEN** ningún servicio declara `ports`, y `frontend` y `api` declaran su puerto interno con `expose`

#### Scenario: Sin nombres fijos de contenedor

- **WHEN** se inspecciona el compose de producción
- **THEN** ningún servicio declara `container_name`

### Requirement: Secretos de producción obligatorios y solo por entorno

El compose de producción NUNCA SHALL contener contraseñas o secretos literales. La contraseña
de Postgres, `JWT_SECRET`, `SEED_ADMIN_PASSWORD`, `CORS_ORIGINS` y `VITE_API_URL` SHALL venir
del entorno y el despliegue SHALL fallar si falta alguno.

#### Scenario: Sin credenciales hardcodeadas

- **WHEN** se busca `turnos:turnos` o `POSTGRES_PASSWORD: turnos` en el compose de producción
- **THEN** no aparece ninguna credencial literal

#### Scenario: Falta un secreto obligatorio

- **WHEN** se intenta desplegar sin `JWT_SECRET` o sin `POSTGRES_PASSWORD` definidos
- **THEN** compose aborta la interpolación con un mensaje que nombra la variable faltante

#### Scenario: Plantilla de entorno de producción versionada

- **WHEN** se lee `.env.prod.example`
- **THEN** lista `DOMAIN`, `POSTGRES_PASSWORD`, `JWT_SECRET`, `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`, `CORS_ORIGINS`, `VITE_API_URL`, `UVICORN_WORKERS`, `WHATSAPP_MOCK=true`, `JWT_EXPIRE_MIN=30` y `TZ` con placeholders, sin secretos reales, y no queda ignorado por git

### Requirement: Frontend servido como build estático

En producción el frontend SHALL servirse como build estático compilado, nunca con el servidor
de desarrollo de Vite, por HTTP plano en un puerto interno. Rutas desconocidas SHALL resolver a
`index.html` para que funcionen los enlaces públicos de la SPA.

#### Scenario: Imagen sin servidor de desarrollo

- **WHEN** se inspecciona la imagen de producción del frontend
- **THEN** compila con `npm ci` y `npm run build` recibiendo `VITE_API_URL` como build arg, y su etapa final no ejecuta `vite` ni `npm run dev`

#### Scenario: Enlace profundo de la SPA

- **WHEN** un paciente abre `https://<DOMAIN>/lista-espera/<token>`
- **THEN** recibe la SPA y no un 404

### Requirement: API detrás del proxy del panel con orígenes restringidos

La API SHALL ser alcanzable públicamente solo a través del proxy del panel en un host propio
del dominio, confiando en los encabezados reenviados por ese proxy. `CORS_ORIGINS` SHALL
limitarse al origen HTTPS del frontend.

#### Scenario: Llamada desde el frontend publicado

- **WHEN** la SPA servida en `https://<DOMAIN>` llama a la API
- **THEN** la llamada va a `https://api.<DOMAIN>` y el navegador la acepta por CORS con credenciales

#### Scenario: Origen no permitido

- **WHEN** un origen distinto de `https://<DOMAIN>` llama a la API con credenciales
- **THEN** la respuesta no incluye el encabezado CORS que lo autoriza

### Requirement: Migraciones y seed en cada despliegue

Cada despliegue SHALL aplicar las migraciones pendientes y el seed idempotente antes de que
arranquen api y worker. Si la migración falla, api y worker NUNCA SHALL arrancar.

#### Scenario: Despliegue con migraciones pendientes

- **WHEN** se despliega con migraciones nuevas
- **THEN** el servicio de migración aplica `alembic upgrade head` y el seed, termina con éxito, y recién entonces arrancan api y worker

#### Scenario: Migración fallida

- **WHEN** el servicio de migración termina con error
- **THEN** api y worker no arrancan

### Requirement: Servicios endurecidos y autorecuperables

Los servicios de larga vida SHALL reiniciarse automáticamente salvo parada manual y SHALL
declarar healthcheck cuando sirven tráfico o datos. Los procesos de la aplicación NUNCA SHALL
correr como root, y los contextos de build SHALL excluir secretos y artefactos locales.

#### Scenario: Reinicio y salud

- **WHEN** se inspecciona el compose de producción
- **THEN** `frontend`, `api`, `worker`, `db` y `redis` declaran `restart: unless-stopped` y `frontend`, `api`, `db` y `redis` declaran healthcheck

#### Scenario: Usuario no root

- **WHEN** se inspeccionan el Dockerfile del backend y la imagen de producción del frontend
- **THEN** el backend declara un `USER` distinto de root antes del arranque y el frontend usa un servidor estático sin privilegios

#### Scenario: Contexto de build sin secretos

- **WHEN** se inspeccionan los `.dockerignore` de backend y frontend
- **THEN** excluyen `.env`, caches y, en frontend, `node_modules` y `dist`

### Requirement: Runbook de despliegue en Easypanel y respaldo

El repositorio SHALL incluir un runbook paso a paso para Easypanel que cubra proyecto y
servicio Compose, variables de entorno, DNS, dominios con HTTPS, despliegue, migraciones,
respaldo y restauración de la base y actualización, reiterando que los datos son ficticios.

#### Scenario: Operador sigue el runbook

- **WHEN** un operador con Easypanel y un dominio sigue el runbook
- **THEN** encuentra cómo crear el servicio Compose desde el repo, asignar `DOMAIN` al frontend y `api.DOMAIN` al puerto 8000 de la api, ver los logs de `migrate`, hacer `pg_dump`, restaurar y redesplegar

#### Scenario: Convivencia con otras apps del panel

- **WHEN** el servidor ya aloja otras aplicaciones en Easypanel
- **THEN** el runbook indica que el despliegue no usa puertos del host ni nombres fijos de contenedor, por lo que no interfiere con ellas

#### Scenario: Datos ficticios declarados

- **WHEN** se lee el runbook
- **THEN** advierte que la demo opera solo con datos ficticios y que no deben cargarse datos reales
