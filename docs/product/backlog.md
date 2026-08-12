# Backlog del MVP

Fuente: `docs/product/mvp.md`.

## Decisiones de estructura

- Proyecto/repositorio `co-donde-ayudo`; marca pública **Dónde Ayudo** en `dondeayudo.co`.
- Proyecto Python `>=3.12` administrado exclusivamente con `uv` y `pyproject.toml`.
- Código bajo `src/backend/` y `src/frontend/`.
- `src/frontend/` contiene NiceGUI en Python; no es una SPA JavaScript ni un despliegue separado.
- Una sola aplicación. El frontend consume funciones públicas del backend y no accede directamente a PostgreSQL.
- Toda persistencia PostgreSQL pertenece a `src/backend/infrastructure/postgres/`, usa modelos y
  sesiones SQLAlchemy con transacciones, y se conecta mediante el driver Psycopg 3.
- Siguen existiendo exactamente cuatro tablas de aplicación; la ubicación dual se representa con
  tres columnas adicionales en `help_points`, no con tablas de eventos o ubicaciones.
- Las migraciones Python de Alembic viven en `src/alembic/`; no se mantienen archivos `.sql` manuales.
- Se implementa una tarea pequeña por vez, con criterios binarios y prueba primero.

## Fase 1 — flujo principal

### F1-00 — Fundar el proyecto Python — COMPLETADA

- [x] `pyproject.toml` declara Python `>=3.12`.
- [x] Existen `src/backend/__init__.py` y `src/frontend/__init__.py`.
- [x] Una prueba estructural verifica ambos criterios.
- [x] No se instalaron dependencias ni se generó lockfile sin aprobación.

### F1-01 — Dependencias y arranque mínimo — COMPLETADA

- [x] Añadir versiones aprobadas de NiceGUI, SQLAlchemy, Alembic y Psycopg 3 al runtime y pytest al grupo de desarrollo.
- [x] Generar `uv.lock` con `uv`.
- [x] Crear un entrypoint NiceGUI mínimo que importe configuración desde backend.
- [x] Verificar imports y arranque local sin realizar conexiones externas al importar módulos.

### F1-02 — Esquema y catálogo inicial — COMPLETADA

- [x] `src/alembic/versions/0001_initial_schema.py` crea exactamente las cuatro tablas definidas por el MVP.
- [x] Incluye relaciones, constraints, índices mínimos y timestamps.
- [x] Inserta exactamente el catálogo global inicial, sin duplicados.
- [x] La migración no contiene credenciales ni requiere tablas adicionales.
- [x] `0002_help_point_locations.py` agrega `direccion`, `ciudad_afectada` y
  `departamento_afectado` a `help_points` y las categorías globales `Remoción de escombros` y
  `Maquinaria pesada`, ambas en `Apoyo`, sin crear una quinta tabla.

### F1-03 — Backend de Punto de ayuda — COMPLETADA

- [x] Crear el modelo de un Punto con varias necesidades mediante una interfaz backend explícita.
- [x] Generar `admin_token` con `secrets.token_urlsafe()` y no exponerlo en vistas públicas.
- [x] Validar campos, longitudes y coordenadas, incluida la dirección física y la zona afectada.
- [x] Probar creación, token correcto y rechazo de token incorrecto.
- [x] Persistir el Punto y sus necesidades mediante SQLAlchemy, Psycopg 3 y `DATABASE_URL`.

### F1-04 — Creación desde NiceGUI — COMPLETADA

- [x] El botón público de creación lleva a `/acceso` y `/crear` redirige allí sin sesión.
- [x] `/acceso` autoriza únicamente una clave válida y guarda solo un booleano en la sesión firmada.
- [x] Ningún secreto aparece en URLs, HTML, respuestas, logs o pruebas.
- [x] La ruta de creación separa la zona afectada de la ubicación física, exige dirección o
  referencia y permite seleccionar varias necesidades.
- [x] **Buscar en el mapa** consulta Nominatim solo por acción explícita; éxito mueve el marker y
  fallo conserva la dirección y permite ubicarlo manualmente.
- [x] Permite crear una categoría no global cuando no existe.
- [x] Al publicar muestra el enlace administrativo privado una sola vez de forma clara.
- [x] `src/frontend/` no accede a PostgreSQL.

### F1-05 — Vista pública — COMPLETADA

- [x] Lista únicamente Puntos activos con sus necesidades y estados textuales.
- [x] Usa el título exacto **¿Dónde ayudo?**, superficie principal blanca y panel de filtros gris
  neutro con selectores blancos.
- [x] Inicia con el mapa y filtra la zona afectada únicamente por Caldas, Chocó, Quindío, Risaralda
  y Valle del Cauca, con ciudad o municipio dependiente.
- [x] El mapa conserva las coordenadas físicas; lista, popup y detalle distinguen **Recibe ayuda
  en:** de **Ayuda destinada a:**.
- [x] Las categorías aparecen dentro de cada Punto, no como filtro público.
- [x] No expone `admin_token` ni datos administrativos.
- [x] Toda la fila compacta enlaza a `/puntos/{point_id}` y muestra únicamente contenido público del Punto activo, sin timestamp ni CTA visible.
- [x] La lista es legible en viewport móvil.

### F1-06 — Administración de un Punto

- [ ] El enlace privado administra solamente su Punto.
- [ ] Permite editar descripción y contacto.
- [ ] Permite agregar, quitar y cambiar el estado de necesidades.
- [ ] Permite desactivar el Punto; deja de aparecer públicamente.
- [ ] Pruebas cubren agregar, quitar, cambiar estado y desactivar.

### F1-07 — Gate de Fase 1

- [ ] El flujo acceder → crear → seleccionar → publicar → administrar → cambiar estado → agregar/quitar funciona completo.
- [ ] Todos los tests configurados pasan con `uv run pytest`.
- [ ] Una revisión independiente no encuentra fallos bloqueantes de alcance, privacidad o seguridad.

## Fases posteriores

- Fase 2: ofrecimientos de ayuda y visualización administrativa de commitments.
- Fase 3: la base prevista para ubicación física en Leaflet y búsqueda explícita con Nominatim se
  incorporó anticipadamente a F1-04 por decisión aprobada; cualquier trabajo posterior se limita a
  mejoras de esa experiencia, sin otro proveedor ni otra tabla.
- Fase 4: móvil, validación final, errores, Docker, README, tests y revisión de seguridad.

No iniciar una fase posterior antes de aprobar el gate de la fase anterior.
