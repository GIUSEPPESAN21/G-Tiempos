# -*- coding: utf-8 -*-
"""
Aplicación de Gestión de Tareas y Tiempos con Streamlit.

Versión 2.0: Se añade una pestaña "Acerca de" para mostrar la información
del autor y de la aplicación, reestructurando la interfaz principal.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO
import altair as alt

# --- Lógica de Negocio y Manejo de Datos ---

class TimeTaskManager:
    """
    Gestiona toda la lógica de la aplicación, incluyendo la manipulación de datos
    de empleados, tareas y registros de tiempo.
    """
    def __init__(self):
        """Inicializa el estado de la sesión para almacenar los DataFrames."""
        if 'registros_df' not in st.session_state:
            # DataFrame para los registros de tiempo de cada tarea
            st.session_state.registros_df = pd.DataFrame(columns=[
                'id_registro', 'nombre_empleado', 'nombre_tarea',
                'tiempo_real', 'tiempo_estipulado', 'fecha_registro'
            ])
            # Asegurar tipos de datos correctos desde el inicio
            st.session_state.registros_df = st.session_state.registros_df.astype({
                'id_registro': str, 'nombre_empleado': str, 'nombre_tarea': str,
                'tiempo_real': float, 'tiempo_estipulado': float,
                'fecha_registro': 'datetime64[ns]'
            })

        if 'tareas_df' not in st.session_state:
            # DataFrame para las definiciones de tareas y sus tiempos estándar
            st.session_state.tareas_df = pd.DataFrame(columns=['nombre_tarea', 'tiempo_estipulado_base'])

    def get_all_data(self):
        """Devuelve todos los DataFrames del estado de la sesión."""
        return st.session_state.registros_df, st.session_state.tareas_df

    def add_task_record(self, empleado, tarea, tiempo_real, tiempo_estipulado_base):
        """
        Añade un nuevo registro de tarea y actualiza o crea la definición de la tarea.
        """
        # --- 1. Gestionar la definición de la Tarea ---
        tarea_existente = st.session_state.tareas_df[
            st.session_state.tareas_df['nombre_tarea'].str.lower() == tarea.lower()
        ]

        if not tarea_existente.empty:
            # La tarea ya existe, usar su tiempo estipulado si no se proporciona uno nuevo
            idx = tarea_existente.index[0]
            if pd.notna(tiempo_estipulado_base) and tiempo_estipulado_base > 0:
                # Si se proporciona un nuevo tiempo, actualizarlo
                st.session_state.tareas_df.loc[idx, 'tiempo_estipulado_base'] = tiempo_estipulado_base
                tiempo_estipulado_snapshot = tiempo_estipulado_base
                st.toast(f"Tiempo base para '{tarea}' actualizado a {tiempo_estipulado_base} min.", icon="🔄")
            else:
                # Usar el tiempo existente
                tiempo_estipulado_snapshot = st.session_state.tareas_df.loc[idx, 'tiempo_estipulado_base']
        else:
            # La tarea es nueva, se requiere un tiempo estipulado base
            if pd.isna(tiempo_estipulado_base) or tiempo_estipulado_base <= 0:
                st.error(f"La tarea '{tarea}' es nueva. Debes proporcionar un 'Tiempo Estipulado Base' positivo.")
                return False
            
            nueva_tarea_df = pd.DataFrame([{'nombre_tarea': tarea, 'tiempo_estipulado_base': tiempo_estipulado_base}])
            st.session_state.tareas_df = pd.concat([st.session_state.tareas_df, nueva_tarea_df], ignore_index=True)
            tiempo_estipulado_snapshot = tiempo_estipulado_base
            st.toast(f"Nueva tarea '{tarea}' definida con un tiempo base de {tiempo_estipulado_snapshot} min.", icon="✨")

        # --- 2. Añadir el nuevo Registro ---
        nuevo_registro = {
            'id_registro': f"reg_{int(datetime.now().timestamp())}",
            'nombre_empleado': empleado,
            'nombre_tarea': tarea,
            'tiempo_real': tiempo_real,
            'tiempo_estipulado': tiempo_estipulado_snapshot,
            'fecha_registro': datetime.now()
        }
        
        nuevo_registro_df = pd.DataFrame([nuevo_registro])
        st.session_state.registros_df = pd.concat([st.session_state.registros_df, nuevo_registro_df], ignore_index=True)
        
        st.success(f"¡Tarea '{tarea}' de {empleado} registrada con éxito!")
        return True

    def clear_all_data(self):
        """Elimina todos los datos de la aplicación."""
        # Reinicia ambos DataFrames a su estado vacío inicial
        self.__init__()
        st.warning("Todos los datos han sido eliminados.")

# --- Funciones de Visualización y Reportes ---

def create_timeline_chart(df):
    """Crea un gráfico de línea de tiempo interactivo con Plotly Express."""
    if df.empty:
        return None

    df_chart = df.copy()
    df_chart['fecha_fin'] = df_chart.apply(lambda row: row['fecha_registro'] + timedelta(minutes=row['tiempo_real']), axis=1)
    df_chart['diferencia'] = df_chart['tiempo_real'] - df_chart['tiempo_estipulado']
    
    def get_status(diferencia):
        if diferencia > (df_chart['tiempo_estipulado'].mean() * 0.1): # Más del 10% de desviación
             return "Con Retraso"
        elif diferencia < -(df_chart['tiempo_estipulado'].mean() * 0.1):
             return "Adelantado"
        return "A Tiempo"
        
    df_chart['estado'] = df_chart['diferencia'].apply(get_status)

    fig = px.timeline(
        df_chart,
        x_start="fecha_registro",
        x_end="fecha_fin",
        y="nombre_empleado",
        color="estado",
        title="Línea de Tiempo de Tareas por Empleado",
        hover_name="nombre_tarea",
        hover_data={
            "tiempo_real": True,
            "tiempo_estipulado": True,
            "diferencia": True,
            "estado": True
        },
        color_discrete_map={
            "Con Retraso": "#ef4444", # red-500
            "A Tiempo": "#3b82f6",    # blue-500
            "Adelantado": "#22c55e" # green-500
        },
        labels={"nombre_empleado": "Empleado", "estado": "Estado de Rendimiento"}
    )
    
    fig.update_layout(
        xaxis_title="Fecha y Hora",
        yaxis_title="Empleado",
        legend_title="Rendimiento",
        font=dict(family="Arial, sans-serif", size=12),
        bargap=0.2
    )
    fig.update_yaxes(categoryorder="total ascending")
    return fig

def create_performance_chart(df):
    """Crea un gráfico de barras para analizar el rendimiento por tarea."""
    if df.empty:
        return None
    
    performance_df = df.groupby('nombre_tarea').agg(
        tiempo_real_avg=('tiempo_real', 'mean'),
        tiempo_estipulado_avg=('tiempo_estipulado', 'first')
    ).reset_index()

    performance_df = performance_df.melt(
        id_vars='nombre_tarea', 
        value_vars=['tiempo_real_avg', 'tiempo_estipulado_avg'],
        var_name='tipo_de_tiempo',
        value_name='minutos'
    )
    performance_df['tipo_de_tiempo'] = performance_df['tipo_de_tiempo'].map({
        'tiempo_real_avg': 'Promedio Real',
        'tiempo_estipulado_avg': 'Estipulado'
    })

    chart = alt.Chart(performance_df).mark_bar().encode(
        x=alt.X('nombre_tarea:N', title='Tarea', sort='-y'),
        y=alt.Y('minutos:Q', title='Minutos'),
        color=alt.Color('tipo_de_tiempo:N', title='Tipo de Tiempo',
                        scale=alt.Scale(domain=['Promedio Real', 'Estipulado'],
                                        range=['#ef4444', '#3b82f6'])),
        tooltip=[
            alt.Tooltip('nombre_tarea:N', title='Tarea'),
            alt.Tooltip('minutos:Q', title='Minutos', format='.1f'),
            alt.Tooltip('tipo_de_tiempo:N', title='Tipo')
        ]
    ).properties(
        title='Comparativa de Tiempos: Real vs. Estipulado'
    )
    return chart

def generate_excel_report(registros_df):
    """Genera un reporte en formato Excel a partir del DataFrame de registros."""
    if registros_df.empty:
        return None
        
    df_report = registros_df.copy()
    df_report['diferencia'] = df_report['tiempo_real'] - df_report['tiempo_estipulado']
    df_report['fecha_registro'] = df_report['fecha_registro'].dt.strftime('%Y-%m-%d %H:%M')
    
    df_report = df_report[[
        'fecha_registro', 'nombre_empleado', 'nombre_tarea',
        'tiempo_estipulado', 'tiempo_real', 'diferencia'
    ]]
    df_report.columns = [
        'Fecha de Registro', 'Nombre del Empleado', 'Nombre de la Tarea',
        'Tiempo Estipulado (min)', 'Tiempo Real (min)', 'Diferencia (min)'
    ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_report.to_excel(writer, index=False, sheet_name='Reporte de Tiempos')
    
    return output.getvalue()

# --- Interfaz de Usuario de Streamlit ---

st.set_page_config(page_title="Gestión de Tiempos", layout="wide", page_icon="🗓️")

manager = TimeTaskManager()
registros, tareas = manager.get_all_data()

st.title("🗓️ Gestión de Tareas y Tiempos")

# --- Pestañas de Navegación ---
tab_registro, tab_dashboard, tab_reportes, tab_acerca_de = st.tabs([
    "✍️ Registrar Tarea", 
    "📊 Dashboard", 
    "📄 Datos y Reportes",
    "ℹ️ Acerca de"
])

# --- Pestaña 1: Registro de Tareas ---
with tab_registro:
    st.header("Formulario de Registro")
    st.markdown("Utilice este formulario para añadir un nuevo registro de tiempo para un empleado y una tarea específica.")

    with st.form("registro_tarea_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            empleado = st.text_input("Nombre del Empleado*", placeholder="Ej: Laura Vargas")
            
            tareas_existentes = ["Nueva Tarea..."] + sorted(tareas['nombre_tarea'].unique().tolist())
            tarea_seleccionada = st.selectbox("Nombre de la Tarea*", options=tareas_existentes)
            
            nombre_tarea_final = ""
            if tarea_seleccionada == "Nueva Tarea...":
                nombre_tarea_final = st.text_input("Nombre de la Nueva Tarea", key="nueva_tarea_input")
            else:
                nombre_tarea_final = tarea_seleccionada

        with col2:
            tiempo_real = st.number_input("Tiempo Real Empleado (minutos)*", min_value=0.1, step=1.0, format="%.2f")
            tiempo_estipulado_base = st.number_input(
                "Tiempo Estipulado Base (minutos)",
                min_value=0.0, step=1.0, format="%.2f", help="Rellena esto solo si es una tarea nueva o si quieres actualizar su tiempo estándar."
            )
        
        submitted = st.form_submit_button("Guardar Registro", type="primary", use_container_width=True)
        if submitted:
            if not empleado or not nombre_tarea_final or not tiempo_real:
                st.warning("Por favor, completa todos los campos obligatorios (*).")
            else:
                manager.add_task_record(empleado, nombre_tarea_final, tiempo_real, tiempo_estipulado_base)

# --- Pestaña 2: Dashboard de Análisis ---
with tab_dashboard:
    st.header("Visualización de Datos")

    st.subheader("Línea de Tiempo de Productividad")
    timeline_chart = create_timeline_chart(registros)
    if timeline_chart:
        st.plotly_chart(timeline_chart, use_container_width=True)
    else:
        st.info("No hay datos registrados para mostrar en la línea de tiempo. Registra una tarea para empezar.")

    st.divider()

    st.subheader("Análisis de Rendimiento por Tarea")
    performance_chart = create_performance_chart(registros)
    if performance_chart:
        st.altair_chart(performance_chart, use_container_width=True)
    else:
        st.info("No hay suficientes datos para generar un análisis de rendimiento.")

# --- Pestaña 3: Datos y Reportes ---
with tab_reportes:
    st.header("Registros y Acciones")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Exportar Datos")
        excel_data = generate_excel_report(registros)
        if excel_data:
            st.download_button(
                label="📄 Descargar Reporte en Excel",
                data=excel_data,
                file_name=f"reporte_tiempos_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("No hay datos para exportar.")

    with col2:
        st.subheader("Zona de Peligro")
        if st.button("🗑️ Limpiar Todos los Datos", type="secondary", use_container_width=True, help="Elimina permanentemente todos los registros y definiciones de tareas."):
            manager.clear_all_data()
            st.rerun()

    st.divider()
    
    st.subheader("Tabla de Registros")
    st.dataframe(registros, use_container_width=True)

# --- Pestaña 4: Acerca de ---
with tab_acerca_de:
    with st.container(border=True):
        st.header("Sobre el Autor y la Aplicación")
        
        _, center_col, _ = st.columns([1, 1, 1])
        with center_col:
            st.image("https://placehold.co/250x250/2B3137/FFFFFF?text=J.S.", width=250, caption="Joseph Javier Sánchez Acuña")

        st.title("Joseph Javier Sánchez Acuña")
        st.subheader("_Ingeniero Industrial, Experto en Inteligencia Artificial y Desarrollo de Software._")
        
        st.markdown("---")
        
        st.subheader("Acerca de esta Herramienta")
        st.markdown("""
        Esta aplicación fue desarrollada para la **gestión y análisis de tiempos y tareas**. El objetivo es ofrecer a equipos y gerentes una forma visual e interactiva de rastrear la productividad, comparar el desempeño real contra los estándares y exportar datos fácilmente para su posterior análisis.

        Desde el registro de tareas individuales hasta la visualización en un dashboard con líneas de tiempo y gráficos de rendimiento, cada funcionalidad está diseñada para facilitar la toma de decisiones basada en datos y mejorar la eficiencia operativa.
        """)

        st.markdown("---")

        st.subheader("Contacto y Enlaces Profesionales")
        st.markdown(
            """
            - 🔗 **LinkedIn:** [joseph-javier-sánchez-acuña](https://www.linkedin.com/in/joseph-javier-sánchez-acuña-150410275)
            - 📂 **GitHub:** [GIUSEPPESAN21](https://github.com/GIUSEPPESAN21)
            - 📧 **Email:** [joseph.sanchez@uniminuto.edu.co](mailto:joseph.sanchez@uniminuto.edu.co)
            """
        )

