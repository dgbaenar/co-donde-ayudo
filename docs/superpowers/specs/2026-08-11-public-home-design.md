# Home público: mapa y lista compacta

## Decisión

El inicio público usa un diseño móvil **mapa + lista compacta**. Una persona entra sin iniciar
sesión y ve inmediatamente los Puntos de ayuda activos. El mapa comunica dónde están; la lista
permite comparar rápidamente qué necesita cada Punto.

## Jerarquía de la página

1. Encabezado compacto con la marca **Dónde Ayudo** y la acción secundaria
   **Coordinar un punto**, que lleva a `/acceso`.
2. Título **¿Dónde necesitan ayuda?** y una explicación breve.
3. Bloque **Filtrar puntos por ubicación**.
4. Mapa Leaflet con los Puntos activos resultantes.
5. Encabezado **Puntos que necesitan ayuda — N resultados**.
6. Lista compacta con los mismos Puntos mostrados en el mapa.

El encabezado, la explicación y los filtros permanecen compactos para priorizar el mapa. En
teléfono, mapa y lista se apilan. En computador, un contenedor amplio presenta el mapa y la lista
en columnas de proporción aproximada 3:2; no se crean vistas o rutas distintas.

## Filtros de ubicación

- Departamento inicia con **Todos los departamentos**.
- Ciudad inicia con **Todas las ciudades**.
- Las opciones proceden únicamente de Puntos activos existentes; el público no escribe texto.
- Al seleccionar un departamento, Ciudad muestra únicamente ciudades de ese departamento.
- Si la ciudad seleccionada deja de pertenecer al departamento, vuelve a **Todas las ciudades**.
- Cada cambio actualiza mapa, contador y lista automáticamente.
- No existe botón **Aplicar filtros**.

## Mapa y lista

- El mapa se centra inicialmente en Colombia y muestra un marcador por Punto activo filtrado.
- El popup conserva nombre, ciudad, departamento, necesidades con texto de estado y
  **Ver punto**.
- La lista muestra nombre, ciudad y departamento, hasta tres necesidades con estado textual y,
  cuando existan más, **+N necesidades**. Para que el resultado sea estable y útil, se ordenan
  primero por estado (**Se necesita**, **Ayuda en camino**, **Cubierto**) y luego por nombre de
  categoría. Todo el contenido de la fila pertenece al enlace del mismo detalle público.
- Mapa, contador y lista siempre consumen el mismo conjunto filtrado.
- Los Puntos inactivos no aparecen.

## Estados

- Sin Puntos activos: el mapa permanece visible y la lista muestra
  **Todavía no hay puntos de ayuda activos.**
- Sin resultados para los filtros: mapa sin marcadores, contador en cero y mensaje
  **No encontramos puntos en esta ubicación. Prueba con otro departamento o ciudad.**
- No se introduce geolocalización, búsqueda, distancia, rutas, categorías como filtro ni GIS
  adicional.

## Límites técnicos

- NiceGUI y el componente Leaflet existente.
- Sin dependencias nuevas, tablas nuevas ni cambios de backend.
- `src/frontend/pages/home.py` compone la página y el filtrado.
- `src/frontend/components/help_point_map.py` conserva la responsabilidad del mapa y popups.
- La ruta pública y la protección de `/crear` no cambian.

## Verificación

- La carga inicial entrega todos los Puntos activos al mapa y la lista.
- Departamento reduce las ciudades disponibles y filtra ambos resultados.
- Ciudad filtra mapa y lista sin botón adicional.
- Cambiar departamento limpia una ciudad incompatible.
- Después de cada cambio, los identificadores de las filas coinciden con los Puntos enviados al
  mapa y con el contador, incluido el resultado cero.
- Ambos estados vacíos usan su mensaje específico y el CTA de coordinación lleva a `/acceso`.
- Las clases estructurales conservan controles táctiles, contenedor amplio, apilado móvil y grid
  de dos columnas 3:2 desde `lg`.
