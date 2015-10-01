===============
CSV Importación
===============

El módulo CSV import es un módulo que amplia las funcionalidades por defecto de importación
de CSV que lleva Tryton por defecto.

Este módulo le permite a parte de añadir nuevos registros al sistema (cualquier modelo)
también le permite la actualización de registros.

Este módulo soporta importaciones complejas hasta dos niveles, por ejemplo:

* Productos
* Productos y variantes
* Tercero y direcciones
* Venta y líneas
* Compra y líneas
* Facturas y líneas

Para importaciones más complejas, se recomienda ya usar módulos de importación propios o conectores
con las plataformas orígen de los datos (mediante webservices).

.. inheritref:: csv_import/csv_import:section:archivos

Archivos
========

Desde el menú |menu_csv_archive| podrá importar datos mediante ficheros CSV.
Los archivos a importar van relacionados con un perfil. El perfil contiene la información
de la estructura del fichero.

Cuando accione la acción de importar fichero CSV por cada línea del CSV a importar
se irá calculando y guardar o actualizar los registros. La información del proceso o en el caso
que haya un error, lo encontrará en la información de logs del archivo.

.. |menu_csv_archive| tryref:: csv_import.menu_csv_archive/complete_name

.. inheritref:: csv_import/csv_import:section:perfiles

Perfiles
========

Los perfiles le permiten diseñar una estructura de como se debe procesar los
ficheros para que cuando quiera importar un fichero CSV no deba configurar cada vez
como es el fichero y que datos contiene.

En los perfiles le permiten:

* Especificar que mapeos se va a usar. Los mapeos van relacionados que objectos y campos
  van a ser importados los datos (véase la sección Base External Mapping)
* Especificar el formato de CSV que va a usar.
* Crear y/o actualizar. Si crearan o actualizarán datos
* Simulación. No crea ni actualiza; es un simulacro.

Para la gestión de los perfiles accede al menú |menu_csv_profile|.

.. |menu_csv_profile| tryref:: csv_import.menu_csv_profile/complete_name

.. inheritref:: csv_import/csv_import:section:ejemplos

Ejemplos
========

Importación de terceros y dirección
-----------------------------------

Un tercero puede disponer de varias direcciones. En este ejemplo de fichero podremos
crear el tercero ya con una dirección.

.. code-block:: csv

    "name","street","city"
    "Zikzakmedia","Dr. Fleming, 28","Vilafranca del Penedès"
    "Raimon Esteve","Dr. Fleming, 28","Vilafranca del Penedès"

Deberemos crear dos mapeos relacionado con el perfil:

* Tercero (party)

  * name (nombre

* Dirección (party.address)

  * Calle (street)
  * Ciudad (city)

En el mapeo deberá relacionar el "Campo CSV relacionado" con "addresses"

Importación de terceros y direcciones
-------------------------------------

Un tercero puede disponer de varias direcciones. En este ejemplo de fichero podremos
crear el tercero ya con varias direcciones

.. code-block:: csv

    "name","street","city"
    "Zikzakmedia","Dr. Fleming, 28","Vilafranca del Penedès"
    "","LLuís Companys, 3","Vilafranca del Penedès"
    "","Francesc Macià, 34","Vilafranca del Penedès"
    "Raimon Esteve","Dr. Fleming, 28","Vilafranca del Penedès"
    "","Durruti, 76","Vilafranca del Penedès"

En este ejemplo, las direcciones extras se encuentran en una nueva línea

Crearemos dos mapeos nuevos o usaremos los mapeos del ejemplo anterior.

Actualización datos de un tercero
---------------------------------

En este ejemplo veremos la opción de actualizar un tercero y código cliente.

En el perfil debemos activar la opción "Actualizar" y rellenar el campo que usaremos
como "identificador a Tryton" (en este ejemplo el nombre) y en que posición el nombre
se encuentra el campo a buscar (en este ejemplo la posición 0 -zero-)

.. code-block:: csv

    "name","code"
    "Zikzakmedia","C1"
    "Raimon Esteve","C2"

Deberemos crear un mapeo relacionado con el perfil:

* Tercero (party)

  * Nombre (name)
  * Código (code)
