=====================================
CSV. Importación ficheros CSV (Mapeo)
=====================================

Importa registros desde ficheros CSV.

Configuración
-------------

El servidor de Tryton debe disponer activo el sistema de fichero (data_path),
como también activar un servidor SMTP para el envío de correo.

Perfiles y archivos
-------------------

- Crea perfiles de importación. Los perfiles le permiten diseñar la estructura
del fichero CSV a importar.
- Crea archivos de importación. Añade un nuevo fichero relacionado con el perfil
y importe sus datos.

Simulación
----------

Los perfiles disponen de la opción simulación. Esta opción no hará la tarea de
guardar y podrá simular la importación (la simulación no soporta los dominios
de los campos en el momento de guardar).

Tipos de ficheros CSV
---------------------

Podemos importar dos tipos de ficheros:
- En cada linia contiene toda la información. Por ejemplo, tercero y dirección

"name","street","city"
"Zikzakmedia","Dr. Fleming, 28","Vilafranca del Penedès"

- En cada linia contiene la información básica, y la siguiente línea la información
de otro registro relacionado con el anterior. Por ejemplo, tercero y direcciones.

"name","street","city"
"Zikzakmedia","Dr. Fleming, 28","Vilafranca del Penedès"
"","LLuís Companys, 3","Vilafranca del Penedès"
"","Francesc Macià, 34","Vilafranca del Penedès"
