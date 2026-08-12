# Diseño web responsive de Dónde Ayudo

## Objetivo

Hacer que la misma aplicación web NiceGUI sea clara y operable en navegadores de computador,
Safari en iPhone y Chrome en Android, sin crear aplicaciones móviles separadas.

## Alcance

- Mantener las rutas actuales: `/`, `/crear` y `/administrar/{admin_token}`.
- Mantener una sola columna centrada: compacta en móvil y con un ancho máximo mayor en escritorio.
- Facilitar navegación, lectura y acciones táctiles en las tres páginas.
- Reutilizar los datos y handlers backend existentes.
- Mantener la interfaz en español y los textos públicos de los estados.

Quedan fuera PWA, instalación en el dispositivo, trabajo offline, aplicaciones nativas, mapas,
notificaciones, nuevas tablas, nuevos endpoints y nuevas dependencias.

## Arquitectura

Los cambios pertenecen exclusivamente a `src/frontend/pages/` y sus pruebas. Cada página conserva
su responsabilidad de presentación y consume las interfaces backend ya inyectadas por
`src/frontend/app.py`. No se modifica la composición de rutas ni la persistencia.

No se introduce una capa de estilos nueva: el corte es lo bastante pequeño para usar las clases
responsive de NiceGUI y Tailwind directamente en cada página sin crear abstracciones especulativas.

## Comportamiento por página

### Inicio

- Mostrar un llamado principal `Crear punto de ayuda` que navegue a `/crear`.
- Mantener los filtros permitidos por ciudad, departamento y categoría.
- Hacer que filtros y acción principal ocupen el ancho del contenedor.
- Mostrar `No hay puntos que coincidan con estos filtros.` cuando el resultado esté vacío.
- Mantener nombres, ubicación, descripción, necesidades y estados visibles sin desplazamiento
  horizontal.

### Creación

- Mantener los campos y el flujo de publicación actuales.
- Hacer que inputs, textarea, selector de necesidades y acción principal ocupen todo el ancho.
- Dar a las acciones principales una altura táctil mínima de 44 px.
- Mantener el enlace administrativo privado como resultado de la publicación.

### Administración

- Resolver cada `category_id` con el catálogo ya inyectado y mostrar el nombre de la necesidad, no
  el UUID.
- Mostrar el estado con su texto público en español.
- Sustituir la fila de cuatro botones técnicos por un selector de estado y una acción
  `Guardar estado`, apilados y de ancho completo.
- Mantener agregar, quitar, editar y desactivar, con acciones principales de ancho completo y altura
  táctil mínima de 44 px.

## Adaptación de pantalla

- Móvil de referencia: viewport de 375 px de ancho.
- Escritorio de referencia: viewport de 1440 px de ancho.
- Contenedor: `w-full max-w-md md:max-w-2xl mx-auto gap-3 p-4`.
- Flujo de una columna en ambos tamaños; no se crea una interfaz distinta por plataforma.
- No debe existir desplazamiento horizontal, solapamiento de controles ni texto técnico truncado.

## Manejo de errores

Se conserva el manejo actual mediante `ui.notify(..., type="negative")`. Los cambios responsive no
alteran validaciones, permisos ni contratos de los handlers.

## Pruebas y aceptación

1. Inicio contiene un enlace visible `Crear punto de ayuda` dirigido a `/crear`.
2. Inicio muestra un estado vacío explícito cuando no hay coincidencias.
3. Los controles principales de creación y administración usan el ancho disponible y acciones de
   al menos 44 px de alto.
4. Administración muestra nombres de categorías y textos públicos de estado; no usa UUID ni valores
   técnicos como etiqueta principal.
5. La selección de estado delega al mismo handler backend con el `NeedStatus` elegido.
6. Las tres rutas conservan su comportamiento a 375 px y 1440 px sin scroll horizontal.
7. La suite completa pasa con `uv run pytest -q`.
8. Una revisión en navegador confirma inicio, creación y administración en viewport móvil y
   escritorio.

## Dependencias y datos

No se añaden paquetes, variables de entorno, migraciones ni datos. El mapping
`Mapping[str, UUID]` existente es suficiente para filtros, selecciones y nombres de categorías.
