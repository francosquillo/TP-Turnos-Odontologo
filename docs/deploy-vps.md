# Despliegue en VPS con Easypanel (C-15)

Runbook para publicar la demo como **un único servicio Compose** de Easypanel usando
`compose.prod.yml`. HTTPS y dominios los gestiona el panel (Traefik + Let's Encrypt).

> **Aviso:** la demo opera solo con datos 100 % ficticios. No cargar datos reales de pacientes.

## Requisitos

- Easypanel instalado en el VPS, un dominio (`DOMAIN`) y acceso a su DNS.
- El repositorio accesible por Git (si es privado, agregar la deploy key SSH de solo lectura).
- Swap recomendado: el build de Node (`npm ci` + `tsc`) usa ~1 GB de RAM; conviene desplegar
  fuera del horario de uso de otras apps del panel (`calculadora-front`, `calculadora-back`).

## Pasos

1. **Proyecto.** En Easypanel crear un proyecto nuevo (p. ej. `turnos`).
2. **Servicio Compose.** Crear un servicio de tipo **Compose** con fuente Git: repositorio, branch
   (`main`), **Build Path** `/` y **Docker Compose File** `compose.prod.yml`.
3. **Entorno.** El panel copia el `.env.example` de desarrollo al editor: **reemplazarlo por
   completo** con el contenido de `.env.prod.example` y completar los secretos con
   `openssl rand -hex 32` (contraseña de Postgres, `JWT_SECRET`) más `SEED_ADMIN_PASSWORD`.
   Ajustar `DOMAIN`, `CORS_ORIGINS` (JSON: `["https://DOMAIN"]`) y `VITE_API_URL`
   (`https://api.DOMAIN`). Activar **Create .env file**. Si falta una variable obligatoria el
   deploy aborta nombrándola.
4. **DNS.** Registros A para `DOMAIN` y `api.DOMAIN` apuntando a la IP del VPS.
5. **Dominios (UI del panel, HTTPS activado).**
   - `DOMAIN` → servicio `frontend`, puerto `8080`.
   - `api.DOMAIN` → servicio `api`, puerto `8000`.
   - HSTS es opcional y se agrega como middleware de Traefik en el panel (nginx solo ve HTTP).
   - Nunca apuntar un dominio a `db` ni a `redis`.
6. **Deploy.** Ejecutar **Deploy** y revisar los logs del servicio `migrate`: aplica
   `alembic upgrade head` y el seed idempotente; `api` y `worker` arrancan solo si termina bien.
7. **Login.** Ingresar a `https://DOMAIN` con `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`.
8. **Backup y restore** (desde la consola del contenedor `db` en el panel, o por SSH al VPS con
   `docker exec`):
   ```sh
   # backup
   pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > /tmp/turnos.dump
   # restore
   pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /tmp/turnos.dump
   ```
   Hacer un backup antes de cambiar volúmenes, borrar el servicio o aplicar migraciones riesgosas:
   eliminar el servicio en el panel o usar `down -v` borra `pgdata`.
9. **Actualizar.** Push al branch y **Deploy** (o la URL de Deployment Trigger para CI).
   Rollback: apuntar el servicio al branch/commit anterior y redesplegar; si una migración dañó
   datos, restaurar el último `pg_dump`.
10. **Convivencia con otras apps.** `compose.prod.yml` no publica puertos del host (sin `ports`)
    ni fija `container_name`, y no declara `name:`; por eso no choca con `calculadora-front`
    ni `calculadora-back`. El tráfico entra solo por los dominios del panel.

## Supuestos a confirmar en el primer deploy

- **S-1** Easypanel conecta los servicios a la red de Traefik sin declarar `networks`; si el
  dominio no resuelve el servicio, agregar la red externa que indique el panel.
- **S-2** `build.args` con interpolación (`VITE_API_URL`) se resuelve desde el `.env` generado.
- **S-3** El panel define el nombre del proyecto Compose; los volúmenes `pgdata`/`redisdata`
  quedan prefijados por proyecto.
- **S-4** Hay consola de contenedor en el panel para Compose; si no, usar SSH + `docker exec`.
- **S-5** `depends_on: service_completed_successfully` y `restart` se respetan (el panel usa
  `docker compose up`).

## Verificación posterior

Abrir `https://DOMAIN`, recargar una ruta interna (p. ej. `/agenda`) y revisar la consola del
navegador: no debe haber errores de CSS/JS ni requests fallidos.
