Gestión de Tareas y Tiempos - Aplicación Streamlit
Esta es una aplicación web interactiva construida con Streamlit para la gestión y análisis de tiempos de tareas realizadas por empleados. Permite a los usuarios registrar el tiempo que dedican a diferentes tareas, comparar esos tiempos con los estándares estipulados y visualizar los datos en un dashboard interactivo.

La aplicación es una adaptación moderna de un proyecto originalmente desarrollado con Flask y una interfaz HTML/JavaScript.

Características Principales
Registro de Tareas: Un formulario intuitivo para que los usuarios ingresen el nombre del empleado, la tarea realizada, el tiempo real empleado y, opcionalmente, actualicen el tiempo estándar para ese tipo de tarea.

Dashboard de Análisis:

Línea de Tiempo Interactiva: Un gráfico de Gantt (timeline) que muestra qué empleado trabajó en qué tarea y durante cuánto tiempo, codificado por colores según el rendimiento (a tiempo, adelantado, con retraso).

Gráfico de Rendimiento: Una comparativa de barras que muestra el tiempo promedio real versus el tiempo estipulado para cada tipo de tarea, facilitando la identificación de tareas problemáticas o estimaciones incorrectas.

Gestión de Datos:

Visualización de todos los registros en una tabla de datos clara.

Exportación a Excel: Descarga un reporte completo de todos los registros en un archivo .xlsx con un solo clic.

Limpieza de Datos: Una opción para eliminar todos los datos de la aplicación y empezar de cero.

Persistencia de Datos: La información se mantiene durante la sesión del usuario gracias al manejo de estado de Streamlit.

Estructura del Proyecto
app.py: El script principal de Python que contiene toda la lógica de la aplicación y la definición de la interfaz de usuario con Streamlit.

requirements.txt: El archivo que lista todas las dependencias de Python necesarias para ejecutar el proyecto.

Cómo Ejecutar la Aplicación Localmente
Sigue estos pasos para poner en marcha la aplicación en tu máquina local.

Clonar el Repositorio:

git clone <URL-de-tu-repositorio-en-GitHub>
cd <nombre-del-repositorio>

Crear y Activar un Entorno Virtual (Recomendado):
Esto aísla las dependencias de tu proyecto.

# Crear el entorno
python3 -m venv venv

# Activar en macOS/Linux
source venv/bin/activate

# Activar en Windows
.\venv\Scripts\activate

Instalar las Dependencias:
El archivo requirements.txt contiene todas las librerías necesarias.

pip install -r requirements.txt

Ejecutar la Aplicación Streamlit:
Una vez instaladas las dependencias, ejecuta el siguiente comando en tu terminal:

streamlit run app.py

Streamlit iniciará un servidor local y abrirá la aplicación automáticamente en tu navegador web.

Despliegue en Streamlit Community Cloud
Esta aplicación está lista para ser desplegada gratuitamente en la plataforma de Streamlit.

Sube tu código a un repositorio público en GitHub. Asegúrate de que los archivos app.py y requirements.txt estén en la raíz del repositorio.

Regístrate en Streamlit Community Cloud usando tu cuenta de GitHub.

Desplegar la aplicación:

Desde tu panel de control, haz clic en "New app".

Selecciona el repositorio de GitHub que acabas de subir.

Asegúrate de que la rama (main o master) y el archivo principal (app.py) estén correctamente seleccionados.

Haz clic en "Deploy!".

Streamlit se encargará del resto, instalando las dependencias y poniendo tu aplicación en línea para que puedas compartirla con una URL pública.
