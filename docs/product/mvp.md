# MVP mínimo — Coordinación de ayuda en emergencias

Quiero construir una aplicación web extremadamente sencilla para coordinar ayuda ciudadana durante una emergencia o desastre en Colombia.

La prioridad absoluta es:

**simplicidad, rapidez de desarrollo y utilidad inmediata.**

No quiero construir una plataforma completa de gestión de emergencias.

No agregues funcionalidades que no estén explícitamente solicitadas.

---

# 1. Problema

Durante una emergencia muchas personas quieren ayudar, pero existe poca coordinación.

Ejemplo:

- un punto necesita agua;
- varias personas comienzan a llevar agua;
- eventualmente ya tienen suficiente;
- otras personas siguen llevando agua porque no saben que ya está cubierta;
- mientras otro lugar continúa necesitando ayuda.

La aplicación debe responder solamente:

1. ¿Dónde ayudo?
2. ¿Qué necesitan?
3. ¿Hay personas yendo a ayudar?
4. ¿Todavía lo necesitan o ya está cubierto?

---

# 2. Concepto principal

La entidad principal se llama:

## Punto de ayuda

Puede ser:

- un barrio;
- un edificio;
- un parque;
- una comunidad;
- un albergue;
- un centro de acopio;
- cualquier lugar desde donde se esté coordinando ayuda.

Una persona crea el Punto de ayuda y se convierte en su coordinador.

Indica:

- nombre del lugar;
- dirección o referencia del lugar físico donde se recibe o coordina la ayuda;
- ciudad y departamento de esa ubicación física;
- ciudad o municipio y departamento de la zona afectada que recibirá la ayuda;
- qué ocurrió o qué está ocurriendo;
- qué necesitan.

La ubicación física del Punto y la zona afectada son conceptos distintos. Un Punto puede estar en
Cali y coordinar ayuda destinada a Roldanillo; el mapa muestra Cali y los filtros públicos usan
Roldanillo.

Después puede mantener actualizadas esas necesidades.

---

# 3. Stack

Quiero mantener el proyecto prácticamente todo en Python.

Usar:

- Python 3.12+
- NiceGUI
- NiceGUI + Leaflet para mapas
- Supabase
- PostgreSQL de Supabase
- Psycopg 3 con `DATABASE_URL`
- Pydantic únicamente si resulta útil
- pytest
- uv
- Docker

NO usar SQLite.

NO crear frontend separado.

NO utilizar manualmente:

- React;
- Next.js;
- Vue;
- TypeScript.

NiceGUI puede utilizar JavaScript internamente, pero yo quiero mantener el código de la aplicación principalmente en Python.

Arquitectura:

```text
NiceGUI / Python
        ↓
Aplicación y dominio
        ↓
SQLAlchemy ORM / Alembic
        ↓
Psycopg 3 / DATABASE_URL
        ↓
Supabase (PostgreSQL alojado)
```

Una sola aplicación.

Toda persistencia PostgreSQL pertenece a `src/backend/infrastructure/postgres/` y usa modelos y
sesiones SQLAlchemy con transacciones. Psycopg 3 es el driver y Supabase se usa como PostgreSQL
alojado. Los cambios de esquema se implementan como migraciones Python de Alembic en `src/alembic/`.

---

# 4. No complicar el MVP

NO implementar:

- inteligencia artificial;
- LLM;
- reconocimiento facial;
- scraping;
- WhatsApp;
- redes sociales;
- chat;
- notificaciones;
- emails;
- inventarios;
- cantidades;
- unidades;
- rutas;
- cálculo de distancias;
- seguimiento GPS;
- recomendaciones;
- matching automático;
- perfiles;
- reputación;
- comentarios;
- dashboards;
- analytics;
- microservicios;
- Redis;
- Celery;
- Kafka;
- workers;
- Kubernetes;
- Terraform.

No implementar cosas "por si después sirven".

---

# 5. Base de datos

Usar Supabase como PostgreSQL alojado.

Quiero solamente estas tablas:

```text
help_points
need_categories
needs
commitments
```

---

# 6. Tabla help_points

Representa un Punto de ayuda.

Campos:

```text
id
nombre
descripcion
ciudad
departamento
direccion
ciudad_afectada
departamento_afectado
latitude
longitude
nombre_coordinador
contacto_coordinador
admin_token
activo
created_at
updated_at
```

`id` debe ser UUID.

`ciudad`, `departamento`, `latitude` y `longitude` describen la ubicación física donde se recibe o
coordina la ayuda. `direccion` agrega la dirección o referencia pública de ese lugar.
`ciudad_afectada` y `departamento_afectado` describen la zona que recibirá la ayuda. Para filas
anteriores `direccion` puede ser nula, pero toda creación nueva exige una dirección o referencia
no vacía de máximo 240 caracteres; los dos campos afectados son obligatorios.

`descripcion` responde solamente:

## ¿Qué está pasando en este punto?

Ejemplo:

> Varias familias fueron evacuadas y estamos organizando ayuda desde este parque.

No intentar estructurar esta información.

`admin_token` debe ser un token privado seguro.

`activo` indica si el punto sigue solicitando ayuda.

---

# 7. Tabla need_categories

Las categorías deben almacenarse en Supabase.

Campos:

```text
id
nombre
grupo
es_global
activo
created_at
```

Ejemplo:

```text
Agua | Alimentos y bebidas
Rescatistas | Rescate y salud
Cobijas | Refugio
Voluntarios | Apoyo
```

Las categorías globales se cargan inicialmente en la base de datos.

Los coordinadores NO pueden:

- editar el nombre de una categoría global;
- cambiar su grupo;
- eliminarla del catálogo global.

Eso no se necesita.

---

# 8. Catálogo global inicial

Mantenerlo pequeño.

Usar solamente estas categorías inicialmente.

## ALIMENTOS Y BEBIDAS

- Agua
- Bebidas hidratantes / electrolitos
- Alimentos
- Comida preparada

## RESCATE Y SALUD

- Rescatistas
- Personal médico
- Primeros auxilios
- Tapabocas
- Guantes
- Cascos
- Linternas
- Palas / picas
- Herramientas de rescate

## REFUGIO

- Cobijas
- Colchonetas
- Ropa
- Elementos de aseo
- Pañales
- Alojamiento

## APOYO

- Voluntarios
- Transporte
- Vehículos
- Cargadores / baterías
- Remoción de escombros
- Maquinaria pesada

No añadir más categorías inicialmente.

No duplicar conceptos.

Ejemplos:

- `Voluntarios` aparece una sola vez.
- `Rescatistas` aparece una sola vez.
- `Tapabocas` aparece una sola vez.

No crear categorías individuales para:

- jabón;
- shampoo;
- crema dental;
- papel higiénico;
- toallas húmedas;
- etc.

Todo eso entra en:

**Elementos de aseo.**

Tampoco subdividir demasiado alimentos.

El catálogo debe permanecer pequeño y fácil de leer desde un teléfono.

`Remoción de escombros` y `Maquinaria pesada` pertenecen al grupo `Apoyo` y pueden combinarse con
necesidades como `Voluntarios`, `Palas / picas`, `Herramientas de rescate` y `Vehículos`. No crear
cantidades, inventario, unidades ni un modelo separado de tareas o maquinaria.

---

# 9. Categorías nuevas

Al crear o administrar un Punto de ayuda debe existir:

## + Agregar otra necesidad

Si algo no está en el catálogo, el coordinador puede escribirlo.

Ejemplo:

```text
Alimento para mascotas
```

Crear una nueva fila en `need_categories`:

```text
nombre = "Alimento para mascotas"
grupo = "Otros"
es_global = false
activo = true
```

No necesitamos un sistema complejo de permisos para esto.

La nueva categoría puede quedar almacenada para poder reutilizarse posteriormente.

No construir ningún sistema automático para decidir si debe convertirse en global.

---

# 10. Añadir y quitar necesidades

Es importante diferenciar:

## Categoría

Ejemplo:

`Agua`

de:

## Necesidad del Punto

Ejemplo:

`El Punto San José necesita Agua`.

El coordinador puede añadir o quitar necesidades de SU Punto.

Ejemplo:

Actualmente necesita:

```text
Agua
Rescatistas
Cobijas
```

El coordinador puede pulsar:

```text
+ Agregar necesidad
```

y añadir:

```text
Linternas
```

También puede quitar:

```text
Cobijas
```

del Punto.

Eso NO elimina `Cobijas` del catálogo global.

Simplemente elimina esa necesidad del Punto.

---

# 11. Tabla needs

Campos:

```text
id
help_point_id
category_id
estado
created_at
updated_at
```

Relaciones:

```text
help_point_id → help_points.id
category_id → need_categories.id
```

No guardar:

- cantidad;
- unidad;
- inventario;
- cantidad recibida;
- cantidad pendiente.

---

# 12. Estados

Una necesidad solamente puede tener tres estados.

## NEEDS_HELP

Mostrar:

🔴 **Se necesita**

---

## HELP_ON_THE_WAY

Mostrar:

🟡 **Hay ayuda en camino — todavía se necesita**

Esto NO significa que esté cubierta.

La gente todavía puede pulsar:

**Voy a ayudar**

---

## COVERED

Mostrar:

🟢 **Cubierto — no enviar más**

No permitir nuevos ofrecimientos de ayuda para esa necesidad mientras esté cubierta.

---

# 13. Tabla commitments

Cuando alguien decide ayudar:

```text
commitments
```

Campos:

```text
id
need_id
nombre
nota
activo
created_at
```

Nada más.

No guardar:

- cantidad;
- teléfono;
- email;
- hora estimada;
- ubicación;
- documento.

---

# 14. Voy a ayudar

En una necesidad activa mostrar:

## Voy a ayudar

Al pulsarlo abrir un diálogo.

Campos:

### Nombre

Obligatorio.

### Nota

Opcional.

Ejemplo:

> Voy para allá.

Botón:

## Confirmar

Después mostrar:

> Gracias. Las personas que coordinan este punto podrán ver que hay ayuda en camino.

---

# 15. Página principal

# Dónde Ayudo

Dominio público: `dondeayudo.co`.

Título:

> ¿Dónde ayudo?

Texto:

> Explora el mapa o revisa la lista de puntos activos.

El pin verde y el título comparten el lado izquierdo de una sola fila responsiva. La acción
secundaria **Coordinar un punto** permanece a la derecha y lleva a `/acceso`; no debe abrir
directamente el formulario protegido. El título aparece una sola vez y el subtítulo queda debajo.

Inmediatamente después mostrar un panel neutral y compacto con este contexto exacto:

```text
Emergencia activa
Respuesta al terremoto de Chocó
Encuentra puntos de ayuda para zonas afectadas en Chocó, Caldas, Valle del Cauca, Risaralda y Quindío.
```

El contexto aparece antes de filtros y mapa. No crea un modelo de eventos, selector de fechas,
feed de noticias ni una quinta tabla.

Usar una superficie principal blanca y un panel de filtros gris neutro. Los selectores son blancos;
no usar fondo o borde verde en el panel. Reservar el verde para marca, acciones y estados.

---

# 16. Vista lista

La lista aparece junto al mapa y sigue siendo compacta y legible en móvil.

Cada Punto muestra aproximadamente:

```text
Parque San José

Recibe ayuda en: Calle 5 # 10-20, Cali, Valle del Cauca

Ayuda destinada a: Roldanillo, Valle del Cauca

Varias familias evacuadas están recibiendo ayuda aquí.

🔴 Agua
🔴 Rescatistas
🟡 Alimentos
🟢 Cobijas — no enviar más
```

Toda la fila compacta enlaza al detalle público `/puntos/{point_id}`, que muestra únicamente el
contenido público del Punto activo: nombre, ubicación, descripción, necesidades con estado y su
mapa. No se muestra un timestamp ni una CTA visible dentro de la fila.

La lista y el detalle distinguen siempre la ubicación física con **Recibe ayuda en:** de la zona
afectada con **Ayuda destinada a:**.

El detalle público `/puntos/{point_id}` usa una jerarquía seccionada y neutral:

1. enlace **Volver al mapa**;
2. un único encabezado de nivel uno con el nombre y una descripción separada;
3. secciones **Ayuda destinada a** y **Recibe ayuda en**, en dos columnas desde computador y
   apiladas en móvil;
4. **Necesidades actuales**, con una fila por necesidad y el estado textual completo;
5. **Ubicación del punto de recepción**, con el mapa de coordenadas físicas.

El contenido dinámico se representa como texto seguro, no como HTML crudo. Rojo, ámbar y verde son
señales secundarias del estado; la información no depende únicamente del color.

No crear cards enormes.

Priorizar densidad y legibilidad.

---

# 17. Filtros

Solamente:

- departamento afectado;
- ciudad o municipio afectado, dependiente del departamento.

El selector de departamento afectado contiene exactamente, en este orden:

- Caldas;
- Chocó;
- Quindío;
- Risaralda;
- Valle del Cauca.

La ubicación física del Punto conserva el catálogo completo de Colombia y no limita dónde puede
existir un centro de acopio. Los filtros públicos operan sobre la zona afectada, no sobre la
ubicación física.

Nada de búsqueda avanzada.

Las categorías se muestran como necesidades dentro de cada Punto, no como filtro del inicio.

Los seis selectores de ubicación usan menús móviles acotados, no diálogos de pantalla completa:
`Departamento` y `Ciudad / Municipio` en el inicio; `Departamento afectado`,
`Ciudad / Municipio afectado`, `Departamento del punto` y `Ciudad / Municipio del punto` en la
creación. Todos usan `behavior=menu`, contenido desplazable con altura máxima `40vh` y opciones de
altura normal. El multiselect **Necesidades** es el séptimo selector en alcance y usa el mismo menú
acotado; puede permanecer abierto mientras se eligen varias opciones. Los selects administrativos
**Estado** y **Agregar necesidad** también usan `behavior=menu`; el catálogo de necesidades se
limita a `40vh`. No aplicar este cambio a otros selects administrativos.

---

# 18. Mapa

Mostrar el mapa con Leaflet como vista inicial, acompañado de la lista de Puntos.

Mostrar un marker por Punto activo en su ubicación física. Filtrar por una ciudad o municipio
afectado puede mostrar un marker ubicado en otra ciudad.

Al tocar marker:

```text
Nombre
Recibe ayuda en: Dirección, Ciudad, Departamento
Ayuda destinada a: Ciudad / Municipio, Departamento
Necesidades activas
[Ver punto]
```

Nada más.

No implementar:

- navegación;
- rutas;
- tráfico;
- cálculo de distancia;
- Google Directions;
- heatmaps;
- GIS avanzado.

---

# 19. Crear Punto de ayuda

Ruta:

```text
/crear
```

Esta ruta requiere una sesión de coordinador obtenida mediante `/acceso`. Una visita directa sin
sesión debe redirigir a `/acceso` sin renderizar el formulario.

`/acceso` explica que la clave es para coordinadores de puntos de ayuda o de recolección. Si una
persona no tiene la clave, muestra `Contacto por WhatsApp: dan.barod` como orientación de contacto.
Esto es solo texto informativo: no agrega un enlace, bot ni integración con WhatsApp.

Formulario pequeño.

Campos:

## Nombre del punto

## ¿Qué está pasando en este punto?

## Zona que recibirá la ayuda

- Departamento afectado: únicamente Caldas, Chocó, Quindío, Risaralda y Valle del Cauca.
- Ciudad / Municipio afectado: depende del departamento afectado.

## Dónde se recibe o coordina la ayuda

- Departamento del punto: catálogo completo de Colombia.
- Ciudad / Municipio del punto: depende del departamento del punto.
- Dirección o referencia del lugar: obligatoria para creaciones nuevas.
- Botón **Buscar en el mapa**.
- Mapa editable mediante toque o clic.

## Nombre del coordinador

## Contacto

La búsqueda de dirección usa explícitamente Nominatim/OpenStreetMap mediante un adaptador backend
inyectado y sin dependencias Python nuevas. Solo se ejecuta al pulsar **Buscar en el mapa**; no hay
autocomplete. La consulta combina dirección, ciudad o municipio, departamento y Colombia, se
limita a Colombia y solicita un resultado.

Si encuentra la dirección, centrar el mapa y colocar el marker. El coordinador puede corregirlo
tocando el mapa. Si no hay resultado o el proveedor falla, conservar la dirección escrita, mantener
disponible el mapa y mostrar:

> No encontramos esa dirección. Ubícala tocando el mapa.

Guardar `latitude` y `longitude` de la ubicación física; no publicar sin coordenadas válidas.

---

# 20. Seleccionar necesidades

En creación mostrar el catálogo agrupado.

Ejemplo:

## Alimentos y bebidas

☐ Agua  
☐ Bebidas hidratantes / electrolitos  
☐ Alimentos  
☐ Comida preparada

## Rescate y salud

☐ Rescatistas  
☐ Personal médico  
☐ Primeros auxilios  
☐ Tapabocas  
☐ Guantes  
☐ Cascos  
☐ Linternas  
☐ Palas / picas  
☐ Herramientas de rescate

## Refugio

☐ Cobijas  
☐ Colchonetas  
☐ Ropa  
☐ Elementos de aseo  
☐ Pañales  
☐ Alojamiento

## Apoyo

☐ Voluntarios  
☐ Transporte  
☐ Vehículos  
☐ Cargadores / baterías

Y al final:

## + Agregar otra necesidad

Debe ser posible seleccionar varias rápidamente.

---

# 21. Administración mediante enlace privado

No crear usuarios.

No crear cuentas ni autenticación individual. La ruta pública `/acceso` solicita una clave de
coordinador compartida, configurada mediante `COORDINATOR_ACCESS_KEY`. Una comparación correcta
crea únicamente una sesión firmada de NiceGUI y habilita `/crear`; una comparación incorrecta no
autoriza ni revela secretos.

Al crear un Punto generar:

```text
admin_token
```

con Python `secrets`.

Crear URL:

```text
https://origen-configurado/administrar/<admin_token>
```

Después de la primera publicación exitosa, ocultar el formulario y mostrar únicamente una pantalla
de éxito enfocada:

```text
Punto de ayuda publicado
Este enlace es privado. Cópialo y guárdalo: lo necesitarás para administrar el punto.
[URL absoluta readonly y seleccionable]
[Copiar enlace]
[Abrir administración]
```

Construir la URL absoluta desde el origen de `APP_BASE_URL`: conservar solo esquema y autoridad,
descartar path, query y fragment, y anexar `/administrar/<admin_token>`. La URL visible, copiada y
abierta debe ser la misma.

Antes de cualquier escritura de categoría personalizada o Punto, activar un guard de publicación
y deshabilitar el botón. Los clics repetidos durante la escritura y todos los intentos posteriores
al éxito no ejecutan otro handler. Si la publicación falla, limpiar el guard, reactivar el
formulario y no mostrar ningún enlace privado.

**Copiar enlace** inicia la operación de portapapeles solo al pulsarlo. Un éxito muestra
`Enlace privado copiado.`; un rechazo o portapapeles no disponible muestra
`No se pudo copiar automáticamente. Mantén presionado el enlace y cópialo manualmente.`. Ninguna
notificación incluye URL o token. El campo readonly siempre permite copia manual; en una sesión
HTTP desde teléfono el copiado automático puede no estar disponible.

El estado de éxito no se recupera tras recargar. No agregar sesión, tabla, cuenta ni mecanismo de
recuperación para el enlace.

---

# 22. Panel de administración

Debe administrar solamente un Punto.

Nada de dashboard general.

Mostrar:

## Información pública

Permitir editar:

- descripción;
- contacto.

## Necesidades

Ejemplo:

```text
Agua
🔴 Se necesita

[Se necesita]
[Hay ayuda en camino — todavía se necesita]
[Cubierto — no enviar más]
[Quitar]
```

Y:

```text
Rescatistas
🔴 Se necesita

[Se necesita]
[Hay ayuda en camino — todavía se necesita]
[Cubierto — no enviar más]
[Quitar]
```

## Agregar necesidad

## Zona de peligro

Mostrar el nombre del Punto debajo del título de la página. Usar cards blancas o slate con bordes
sutiles y estas acciones explícitas, todas con objetivo táctil mínimo de 44 px:

- **Guardar información** y **Guardar estado**: botón relleno `green-9`;
- **Agregar necesidad**: botón outlined `green-9`;
- **Quitar**: botón outlined `red-9`;
- **Desactivar punto**: botón relleno `red-9`, únicamente dentro de **Zona de peligro**.

Reservar el rojo para acciones destructivas y no depender solo del color. El selector de estado
usa los textos públicos completos: **Se necesita**, **Hay ayuda en camino — todavía se necesita**
y **Cubierto — no enviar más**.

---

# 23. Quitar una necesidad

Si el coordinador pulsa:

## Quitar

abrir una confirmación explícita. Cancelar no llama al backend; confirmar **Sí, quitar necesidad**
ejecuta exactamente una operación y la necesidad deja de aparecer públicamente en ese Punto.

No eliminar la categoría global.

No afectar otros Puntos.

Implementar esto de la manera más sencilla y segura posible.

Puede ser eliminación de `needs` o un estado interno si resulta necesario.

No crear un complejo sistema de auditoría.

---

# 24. Personas que van a ayudar

En administración mostrar:

## Personas que van a ayudar

Ejemplo:

```text
Agua

Daniel
"Voy para allá."
Hace 12 minutos
```

No necesitamos más información.

---

# 25. Desactivar Punto

Dentro de **Zona de peligro**, botón:

## Desactivar punto

Abrir una confirmación explícita. Cancelar no llama al backend; confirmar **Sí, desactivar punto**
ejecuta exactamente una operación y cambia:


```text
activo = false
```

Los diálogos y notificaciones no muestran el `admin_token`.

Debe desaparecer de la lista y mapa principal.

Si alguien abre directamente su URL mostrar:

> Este punto ya no está solicitando ayuda.

---

# 26. Diseño

Mobile-first.

Debe ser:

- rápido;
- claro;
- sobrio;
- fácil de usar;
- con botones grandes;
- sin decoración innecesaria.

No crear una interfaz estilo SaaS.

No usar:

- dashboards;
- gráficas;
- sidebars;
- animaciones innecesarias;
- gradientes;
- landing page de marketing.

---

# 27. Estados visuales

Usar consistentemente:

🔴 **Se necesita**

🟡 **Hay ayuda en camino — todavía se necesita**

🟢 **Cubierto — no enviar más**

Nunca depender solamente del color.

Siempre mostrar texto.

---

# 28. Seguridad básica

Implementar:

- admin tokens mediante `secrets.token_urlsafe()`;
- tokens suficientemente largos;
- comparación de la clave de coordinador mediante `secrets.compare_digest()`;
- sesión de coordinador firmada mediante `APP_SESSION_SECRET`;
- no incluir secretos en URLs, HTML, respuestas, logs o pruebas;
- validación de inputs;
- límites razonables de longitud;
- validación de latitude y longitude;
- consultas seguras mediante SQLAlchemy, parámetros enlazados y transacciones;
- no exponer admin_token públicamente;
- variables de entorno.

No implementar autenticación compleja.

---

# 29. Variables de entorno

Usar por ejemplo:

```text
DATABASE_URL=
APP_BASE_URL=https://dondeayudo.co
COORDINATOR_ACCESS_KEY=
APP_SESSION_SECRET=
```

No hardcodear credenciales.

Crear:

```text
.env.example
```

---

# 30. Migración PostgreSQL con Alembic

Incluir una migración inicial de Alembic enteramente en Python bajo:

```text
src/alembic/versions/0001_initial_schema.py
```

Debe contener:

- creación de las cuatro tablas;
- relaciones;
- constraints;
- índices mínimos necesarios;
- timestamps;
- inserción de las categorías globales iniciales.

La migración `src/alembic/versions/0002_help_point_locations.py` agrega únicamente a
`help_points` las columnas `direccion`, `ciudad_afectada` y `departamento_afectado`, rellena la zona
afectada de filas existentes desde su ubicación física e inserta las categorías globales
`Remoción de escombros` y `Maquinaria pesada` en el grupo `Apoyo`. No crea una quinta tabla ni
modifica la migración inicial.

Aplicar la migración con:

```bash
uv run alembic -c src/alembic/alembic.ini upgrade head
```

No crear migraciones complejas inicialmente ni archivos de esquema `.sql` manuales.

---

# 31. Estructura

Mantener pocos archivos.

Algo parecido a:

```text
src/
    alembic/
        alembic.ini
        env.py
        versions/
            0001_initial_schema.py
    backend/
        infrastructure/
            postgres/
    frontend/
        pages/
            home.py
            create.py
            point.py
            manage.py

        components/
            map.py
            needs.py

tests/
    test_services.py

pyproject.toml
Dockerfile
.env.example
README.md
```

Reducir incluso esto si es posible.

No crear:

```text
domain/
repositories/
adapters/
ports/
use_cases/
interfaces/
```

YAGNI.

---

# 32. Tests

Pocos tests.

Solamente verificar:

1. visitante sin sesión no accede a `/crear`;
2. clave de coordinador incorrecta no autoriza;
3. clave correcta autoriza una sesión sin exponer secretos;
4. creación de Punto;
5. generación de admin token;
6. acceso con token correcto;
7. rechazo de token incorrecto;
8. agregar necesidad;
9. quitar necesidad;
10. cambiar estado;
11. crear commitment;
12. impedir commitment cuando está `COVERED`;
13. desactivar Punto.

Nada más inicialmente.

---

# 33. Desarrollo por fases

## Fase 1

Construir solamente:

- conexión PostgreSQL mediante Psycopg 3 y `DATABASE_URL`;
- schema;
- categorías;
- creación de Punto;
- selección de necesidades;
- página pública;
- página administrativa;
- agregar/quitar necesidades;
- cambiar estado.

Flujo:

```text
acceder como coordinador
↓
crear punto
↓
seleccionar necesidades
↓
publicar
↓
administrar
↓
cambiar estado
↓
añadir/quitar necesidad
```

Debe funcionar completamente antes de continuar.

---

## Fase 2

Agregar:

- botón Voy a ayudar;
- nombre;
- nota;
- commitments;
- mostrar commitments al coordinador.

---

## Fase 3

La base prevista para esta fase se incorporó anticipadamente al flujo principal por decisión
aprobada: la creación ya incluye selección de la ubicación física en Leaflet, búsqueda explícita
de dirección con Nominatim y fallback manual en el mapa. Cualquier trabajo posterior en esta fase
se limita a mejorar esa experiencia, sin agregar proveedores, tablas ni conceptos nuevos.

---

## Fase 4

Solamente:

- mejorar móvil;
- validaciones;
- manejo de errores;
- Docker;
- README;
- tests;
- revisión básica de seguridad.

La base operativa de Docker, Railway y README se incorporó anticipadamente por decisión aprobada.
La configuración vigente y el procedimiento seguro de publicación y migraciones se documentan en
el [README](../../README.md#despliegue-en-railway); esto no completa por sí solo la validación final
de la Fase 4.

NO añadir features nuevos.

---

# 34. Definición de terminado

El MVP está terminado cuando funciona este flujo:

1. Como visitante, entro a la web y veo el mapa y los Puntos sin iniciar sesión.
2. Como coordinador autorizado, entro a `/acceso` y escribo la clave compartida.
3. Creo un Punto.
4. Escribo qué está pasando.
5. Indico la zona afectada y marco la ubicación física donde se recibe o coordina la ayuda.
6. Selecciono:
   - Agua
   - Alimentos
   - Rescatistas
   - Palas / picas
7. Lo publico.
8. Recibo un enlace privado.
9. Otra persona ve el Punto.
10. Ve exactamente qué necesita.
11. Pulsa "Voy a ayudar" en Agua.
12. Escribe su nombre.
13. El coordinador puede ver que esa persona va a ayudar.
14. El coordinador marca Agua como:
   "Cubierto — no enviar más".
15. Todo el mundo ve el cambio.
16. El coordinador puede quitar Palas / picas.
17. Puede añadir otra necesidad.
18. Puede desactivar completamente el Punto.

Si esto funciona bien desde un teléfono:

**el MVP está terminado.**

---

# 35. Regla fundamental

Antes de implementar cualquier funcionalidad, preguntar:

> ¿Es imprescindible para completar el flujo definido arriba?

Si no:

**NO IMPLEMENTARLA.**

No agregar features porque parezcan útiles.

No anticipar una escala que todavía no existe.

No convertir este proyecto pequeño en una arquitectura empresarial.

Construir primero exactamente este MVP.
