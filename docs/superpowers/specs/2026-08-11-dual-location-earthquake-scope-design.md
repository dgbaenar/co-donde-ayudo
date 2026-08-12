# Diseño — Ubicación dual y alcance del terremoto de Chocó

Fecha: 2026-08-11

## Objetivo

Hacer que Dónde Ayudo distinga claramente entre:

1. la zona afectada que recibirá la ayuda; y
2. el lugar físico donde las personas entregan o coordinan esa ayuda.

El cambio también simplifica el diseño público, incorpora dirección con búsqueda opcional y
mantiene un fallback manual en el mapa. Continúan existiendo exactamente cuatro tablas de
aplicación.

## Alcance territorial operativo

Para el terremoto del 10 de agosto de 2026 con epicentro en Chocó, la zona beneficiaria queda
limitada a estos departamentos, en este orden alfabético:

- Caldas
- Chocó
- Quindío
- Risaralda
- Valle del Cauca

Esta lista es una decisión operativa del producto. Debe vivir en un módulo backend cohesivo e
inyectarse en las páginas; no se creará una tabla de eventos ni una interfaz administrativa para
editarla.

La ubicación física del punto de acopio no se limita a esos departamentos. Debe conservar el
catálogo completo de Colombia porque un punto ubicado, por ejemplo, en Cali puede recibir ayuda
destinada a otro municipio.

## Modelo de ubicación

Los campos existentes conservan su significado físico:

- `city`, `department`, `latitude`, `longitude`: lugar donde se recibe o coordina la ayuda.

Se agregan al Punto de ayuda:

- `address`: dirección o referencia pública del lugar físico;
- `affected_city`: ciudad o municipio que recibirá la ayuda;
- `affected_department`: departamento que recibirá la ayuda.

En PostgreSQL se agregan únicamente estas columnas a `help_points`:

```text
direccion varchar(240) null
ciudad_afectada varchar(120)
departamento_afectado varchar(120)
```

La migración nueva será `0002_help_point_locations.py`. No modificará la migración inicial ni
creará tablas.

Para conservar filas existentes:

- `ciudad_afectada` se rellena inicialmente desde `ciudad`;
- `departamento_afectado` se rellena inicialmente desde `departamento`;
- después del relleno, ambos campos quedan `NOT NULL`;
- `direccion` permanece nullable en la base porque no se puede inventar para filas anteriores;
- las creaciones nuevas exigen una dirección o referencia no vacía de máximo 240 caracteres.

Los modelos de creación, administración y lectura pública transportan los tres campos. La
dirección y la zona beneficiaria son información pública; `admin_token` continúa excluido de toda
representación pública.

## Experiencia pública

La cabecera muestra una sola marca/título:

> ¿Dónde ayudo?

Se elimina completamente la pregunta `¿Dónde necesitan ayuda?`. Se conserva un subtítulo breve
que invita a explorar el mapa o la lista.

El fondo principal será blanco. El panel de filtros será gris neutro, sin borde ni fondo verde.
Los selectores serán blancos y el verde quedará reservado para la marca, acciones y estados.

Los filtros públicos representan la **zona que recibirá la ayuda**:

- departamento afectado, limitado a los cinco departamentos operativos;
- ciudad o municipio afectado, dependiente del departamento.

El mapa representa siempre la **ubicación física del punto**. La lista, el popup y el detalle
distinguen explícitamente:

```text
Recibe ayuda en: [dirección], Cali, Valle del Cauca
Ayuda destinada a: Roldanillo, Valle del Cauca
```

Por tanto, filtrar por Roldanillo puede mostrar un marcador ubicado en Cali. El mapa, el contador y
la lista continúan usando el mismo conjunto filtrado.

## Creación de un Punto

El formulario protegido se divide en dos bloques.

### Zona que recibirá la ayuda

- Departamento afectado: solo los cinco departamentos operativos.
- Ciudad / Municipio afectado: depende del departamento.

### Dónde se recibe o coordina la ayuda

- Departamento del punto: catálogo completo de Colombia.
- Ciudad / Municipio del punto: depende del departamento.
- Dirección o referencia del lugar: obligatoria para nuevas creaciones.
- Botón `Buscar en el mapa`.
- Mapa editable mediante toque o clic.

La ubicación física continúa requiriendo coordenadas válidas antes de publicar.

## Búsqueda de dirección

La opción recomendada y aprobada usa la API pública de Nominatim/OpenStreetMap mediante un
adaptador backend inyectado. No se agrega una dependencia Python.

Comportamiento:

1. La búsqueda ocurre únicamente al pulsar `Buscar en el mapa`; no existe autocomplete.
2. La consulta combina dirección, ciudad/municipio, departamento y Colombia.
3. La consulta se limita a Colombia y solicita un solo resultado.
4. Si encuentra un resultado, centra el mapa y coloca el marcador.
5. El coordinador puede corregir la posición tocando el mapa.
6. Si no encuentra la dirección o el proveedor falla, muestra:
   `No encontramos esa dirección. Ubícala tocando el mapa.`
7. La dirección escrita nunca se borra por un fallo de búsqueda.

El adaptador debe:

- identificar la aplicación con un `User-Agent` propio;
- respetar un máximo de una consulta por segundo por proceso;
- usar timeout corto;
- no registrar la consulta ni datos introducidos;
- no realizar red ni trabajo al importar módulos.

Las pruebas usan un fake local y nunca llaman al servicio real.

## Remoción de escombros

No se crea un modelo nuevo para tareas, herramientas o maquinaria. Las necesidades siguen siendo
categorías combinables.

Se agregan dos categorías globales mediante la migración `0002`:

- `Remoción de escombros`, grupo `Apoyo`;
- `Maquinaria pesada`, grupo `Apoyo`.

El coordinador puede combinarlas con categorías existentes como `Voluntarios`, `Palas / picas`,
`Herramientas de rescate` y `Vehículos`. El formulario explicará que se debe seleccionar tanto la
tarea como los recursos requeridos. No se agregan cantidades, inventario ni unidades.

## Propiedad por capas

- Dominio backend: validación de dirección y zona beneficiaria.
- Aplicación backend: alcance territorial vigente y orquestación existente.
- Infraestructura PostgreSQL: columnas, migración y mapeo ORM.
- Infraestructura de geocoding: única integración con Nominatim.
- Frontend: presentación, interacción, actualización del mapa y mensajes.
- `frontend.app` y `frontend.runtime`: solamente composición e inyección.

Se mantienen imports absolutos y no se añade acceso a PostgreSQL ni a Nominatim desde páginas.

## Manejo de errores

- Departamento afectado fuera del alcance operativo: rechazo antes de persistir.
- Ciudad/municipio que no pertenece al departamento seleccionado: rechazo del formulario.
- Dirección vacía en una creación nueva: mensaje de validación.
- Dirección no encontrada o error de red: selección manual permanece disponible.
- Coordenadas ausentes: no se publica el Punto.
- Fallos de geocoding no bloquean la selección manual ni revelan detalles internos.

## Verificación

Pruebas mínimas:

- dominio valida los tres campos nuevos y el alcance afectado;
- migración agrega columnas y categorías sin crear una quinta tabla;
- filas existentes reciben zona beneficiaria compatible;
- repositorio realiza round-trip de dirección y zona;
- modelos públicos no incluyen `admin_token`;
- filtros usan zona afectada, no ubicación física;
- un punto físico en Cali destinado a Roldanillo aparece al filtrar Roldanillo y conserva el marker
  en Cali;
- selects de zona afectada muestran solo los cinco departamentos;
- selects del punto físico conservan los 33 departamentos;
- geocoding exitoso coloca o mueve el marker;
- geocoding sin resultado y error mantienen el fallback manual;
- lista, popup y detalle muestran ambas ubicaciones;
- creación y enlace administrativo existentes continúan funcionando.

Verificación final:

- pruebas focales y suite completa con `uv run --no-sync pytest -q`;
- consistencia del lockfile con `uv lock --check`;
- navegador real en 1280×900, 390×844 y 375×667;
- sin scroll horizontal, solapamientos ni errores de consola;
- `/crear` continúa redirigiendo a `/acceso` sin sesión;
- no se lee `.env`, no se usan secretos y no se hacen pruebas contra Nominatim real.

## Fuera de alcance

- múltiples zonas beneficiarias por Punto;
- segundo mapa para la zona afectada;
- rutas, navegación o cálculo de distancia;
- autocomplete de direcciones;
- cantidades, inventario o asignación de maquinaria;
- tabla de eventos o panel para administrar el alcance territorial;
- edición de ubicación o destino desde el enlace administrativo;
- proveedor alternativo o fallback automático entre geocoders.

## Criterios de aceptación

El cambio queda terminado cuando:

1. el home usa fondo blanco, filtros neutros y el título exacto `¿Dónde ayudo?`;
2. los filtros públicos ofrecen únicamente Caldas, Chocó, Quindío, Risaralda y Valle del Cauca;
3. crear un Punto distingue destino afectado de ubicación física;
4. la ubicación física puede buscarse por dirección o marcarse manualmente;
5. mapa y filtros usan correctamente sus dos conceptos de ubicación;
6. la interfaz explica claramente dónde se recibe la ayuda y a dónde va destinada;
7. `Remoción de escombros` y `Maquinaria pesada` están disponibles como necesidades globales;
8. siguen existiendo exactamente cuatro tablas;
9. seguridad, autorización y enlace administrativo no sufren regresiones;
10. la experiencia es legible y utilizable en computador, iPhone y Android.
