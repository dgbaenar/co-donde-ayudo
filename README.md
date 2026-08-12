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
en las variables del servidor y nunca se incluye en enlaces.

## Verificación desde un teléfono

Inicia la aplicación y consulta la dirección IP local del Mac:

```bash
uv run donde-ayudo
ifconfig en0 | rg 'inet '
```

Conecta el teléfono y el Mac a la misma red Wi-Fi. Desde el teléfono abre
`http://IP_DE_TU_MAC:8080`, reemplazando `IP_DE_TU_MAC` por la dirección IPv4 mostrada para `en0`.
Si macOS solicita permiso para aceptar conexiones entrantes, concédelo a la aplicación; si no se
puede abrir la página, revisa que el firewall de macOS permita esas conexiones.

## Pruebas

```bash
uv run pytest
```
