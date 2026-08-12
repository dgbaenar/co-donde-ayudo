# Dónde Ayudo

Aplicación web móvil para coordinar puntos de ayuda ciudadana durante emergencias en Colombia.
Dominio público: `dondeayudo.co`.

## Requisitos

- Python 3.12 o superior
- `uv`
- Docker Compose

## Arranque local

El archivo `.env.example` incluye valores de desarrollo para PostgreSQL local. Antes de arrancar,
copia el archivo y define valores privados, largos y distintos para `COORDINATOR_ACCESS_KEY` y
`APP_SESSION_SECRET`. No los confirmes en Git ni los compartas en URLs o logs.

```bash
cp .env.example .env
docker compose up -d postgres
uv run alembic -c src/alembic/alembic.ini upgrade head
uv run donde-ayudo
```

Para usar Supabase, conserva la misma migración y aplicación; sustituye únicamente `DATABASE_URL` por la URL de esa base de datos.

El público usa `/`. Los coordinadores autorizados ingresan por `/acceso`; la clave permanece solo
en las variables del servidor y nunca se incluye en enlaces. Esa pantalla aclara que el acceso es
para quienes coordinan puntos de ayuda o de recolección y muestra `dan.barod` como contacto por
WhatsApp si necesitan solicitar la clave; no integra ni automatiza WhatsApp.

## Despliegue en Railway

El repositorio incluye `Dockerfile` y `railway.toml`. Railway construye la imagen desde el
`Dockerfile`; antes de publicar una versión ejecuta como pre-deploy:

```bash
uv run --no-sync alembic -c src/alembic/alembic.ini upgrade head
```

Si la migración falla, la nueva versión no debe arrancar. Después, Railway inicia la aplicación
con `uv run --no-sync donde-ayudo` y espera una respuesta exitosa de `/readyz`. La aplicación lee
el puerto de `PORT`, que Railway proporciona; localmente usa `8080` por defecto. `/healthz` solo
confirma que el proceso responde, mientras `/readyz` también comprueba la conexión con PostgreSQL.

Configura estas variables en el servicio de Railway, sin escribir sus valores en archivos del
repositorio:

- `DATABASE_URL`
- `APP_BASE_URL`
- `COORDINATOR_ACCESS_KEY`
- `APP_SESSION_SECRET`

`APP_BASE_URL` debe ser el origen HTTPS público y canónico. `DATABASE_URL` puede apuntar al
PostgreSQL del proveedor elegido, incluido Supabase; la aplicación y Alembic usan la misma URL.

### Publicaciones y migraciones seguras

Los tests, el lockfile, la migración pre-deploy y `/readyz` reducen el riesgo de una nueva versión,
pero no garantizan que una migración de datos sea reversible. Antes de aplicar una migración en
producción:

1. registra la revisión instalada y la revisión objetivo con
   `uv run alembic -c src/alembic/alembic.ini current` y
   `uv run alembic -c src/alembic/alembic.ini heads`;
2. crea y verifica un backup o snapshot en el proveedor de PostgreSQL;
3. revisa que la nueva aplicación sea compatible con el esquema durante el despliegue;
4. aplica Alembic antes de cambiar el tráfico;
5. comprueba `/readyz` y el flujo principal tras publicar, y conserva las revisiones registradas
   junto al resultado del despliegue.

La migración existente `0002_help_point_locations` agrega columnas, rellena filas y luego exige
valores no nulos. Para aplicarla por primera vez sobre una base que ya recibe escrituras, programa
una ventana corta sin nuevas creaciones de puntos: activa el bloqueo de escrituras, toma el backup,
ejecuta la migración, publica la aplicación y valida `/readyz` antes de reabrir escrituras.

Un rollback de la aplicación en Railway revierte el código o la configuración desplegada, no el
esquema ni los datos de PostgreSQL. Si una migración ya fue aplicada, prefiere una migración
correctiva hacia adelante. No ejecutes `alembic downgrade` de forma automática: el downgrade de
`0002_help_point_locations` elimina sus columnas de ubicación. Para cambios futuros usa el patrón
expandir → desplegar código compatible → rellenar datos → retirar lo antiguo en otra versión.

## Verificación desde un teléfono

Inicia la aplicación y consulta la dirección IP local del Mac:

```bash
uv run donde-ayudo
ifconfig en0 | rg 'inet '
```

Conecta el teléfono y el Mac a la misma red Wi-Fi. Desde el teléfono abre
`http://IP_DE_TU_MAC:8080`, reemplazando `IP_DE_TU_MAC` por la dirección IPv4 mostrada para `en0`.
Para que el enlace administrativo copiado también funcione desde ese teléfono, define antes de
arrancar la aplicación:

```text
APP_BASE_URL=http://IP_DE_TU_MAC:8080
```

La aplicación construye el enlace privado desde ese origen. En HTTP remoto el navegador puede
rechazar el portapapeles automático; la pantalla de éxito conserva la URL readonly para copiarla
manualmente. En producción usa el origen HTTPS canónico.

Si macOS solicita permiso para aceptar conexiones entrantes, concédelo a la aplicación; si no se
puede abrir la página, revisa que el firewall de macOS permita esas conexiones.

## Pruebas

```bash
uv run pytest
```
