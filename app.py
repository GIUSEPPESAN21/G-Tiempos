# app.py (Versión con correcciones para PDF, WhatsApp y mejoras en Timeline)

from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify, send_file
import os
from datetime import datetime, timedelta, timezone
import uuid
import io
import csv
import statistics # Aunque no se usa activamente ahora, podría ser útil para análisis futuros
import logging

from sqlalchemy import create_engine, Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.pool import StaticPool

# --- ReportLab Imports (para PDF) ---
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT # TA_RIGHT no se usa, se puede quitar


# --- Configuración de Twilio (Credenciales Proporcionadas) ---
TWILIO_ACCOUNT_SID = "ACe6fc51bff702ab5a8ddd10dd956a5313"
TWILIO_AUTH_TOKEN = "63d61de04e845e01a3ead4d8f941fcdd"
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"
DESTINATION_WHATSAPP_NUMBER = "whatsapp:+573222074527"
UMBRAL_SOBRETIEMPO_CRITICO_PORCENTAJE = float(os.environ.get("UMBRAL_SOBRETIEMPO_CRITICO_PORCENTAJE", 30.0)) # Reducido para facilitar pruebas

twilio_client = None
twilio_configured_properly = False

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and \
   TWILIO_WHATSAPP_NUMBER and DESTINATION_WHATSAPP_NUMBER and \
   not TWILIO_ACCOUNT_SID.startswith("ACxxxx") and \
   not TWILIO_AUTH_TOKEN == "your_auth_token_here":
    try:
        from twilio.rest import Client
        from twilio.base.exceptions import TwilioRestException # Importar para manejo de errores específico
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        twilio_configured_properly = True
        logging.info("Cliente de Twilio inicializado correctamente.")
    except ImportError:
        logging.error("Librería Twilio no instalada. Ejecute: pip install twilio")
    except Exception as e:
        logging.error(f"Fallo al inicializar el cliente de Twilio: {e}")
else:
    logging.warning("Credenciales de Twilio no configuradas o son placeholders. Las alertas de WhatsApp no funcionarán.")


# --- Configuración de Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(funcName)s - %(message)s', # Formato más detallado
                    handlers=[logging.StreamHandler()])
app_logger = logging.getLogger('flask.app') # Usar el logger de Flask para consistencia


# --- Configuración de SQLAlchemy ---
DATABASE_URL = "sqlite:///./tareas_timeline_v3.db" # Nueva BD para esta versión con más correcciones
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modelos de Base de Datos (Tablas) ---
class EmpleadoDB(Base):
    __tablename__ = "empleados"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    nombre = Column(String, unique=True, index=True, nullable=False)
    registros = relationship("RegistroTareaDB", back_populates="empleado_rel")

class TareaDefinicionDB(Base):
    __tablename__ = "definiciones_tareas"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    nombre_tarea = Column(String, unique=True, index=True, nullable=False)
    tiempo_estipulado_base = Column(Float, nullable=False)
    registros = relationship("RegistroTareaDB", back_populates="tarea_definicion_rel")

class RegistroTareaDB(Base):
    __tablename__ = "registros_tareas"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    empleado_id = Column(String, ForeignKey("empleados.id"), nullable=False)
    tarea_definicion_id = Column(String, ForeignKey("definiciones_tareas.id"), nullable=False)
    tiempo_real_empleado = Column(Float, nullable=False)
    tiempo_estipulado_snapshot = Column(Float, nullable=False)
    fecha_registro = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    empleado_rel = relationship("EmpleadoDB", back_populates="registros")
    tarea_definicion_rel = relationship("TareaDefinicionDB", back_populates="registros")

Base.metadata.create_all(bind=engine)

# Flask app setup
app = Flask(__name__, template_folder='.')
app.secret_key = os.urandom(24)

# --- Función de Envío de Alerta WhatsApp ---
def enviar_alerta_whatsapp_productividad(mensaje_alerta):
    if not twilio_configured_properly or not twilio_client:
        app_logger.error("ALERTA WHATSAPP NO ENVIADA: Cliente Twilio no configurado o no inicializado.")
        return False
    
    app_logger.info(f"Intentando enviar alerta WhatsApp a {DESTINATION_WHATSAPP_NUMBER} desde {TWILIO_WHATSAPP_NUMBER}")
    try:
        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER, # Ya tiene 'whatsapp:'
            body=mensaje_alerta,
            to=DESTINATION_WHATSAPP_NUMBER # Ya tiene 'whatsapp:'
        )
        app_logger.info(f"ALERTA WHATSAPP: Enviada/Encolada. SID: {message.sid}, Estado: {message.status}. Mensaje: '{mensaje_alerta[:50]}...'") # Loguear solo parte del mensaje
        return True
    except TwilioRestException as e:
        app_logger.error(f"ALERTA WHATSAPP: Error REST de Twilio al enviar mensaje: {e}")
        app_logger.error(f"Detalles del error de Twilio - Status: {e.status}, Code: {e.code}, URI: {e.uri}, Msg: {e.msg}")
        if hasattr(e, 'details') and e.details: app_logger.error(f"Twilio Error Details: {e.details}")
        return False
    except Exception as e: # Capturar otros posibles errores (red, etc.)
        app_logger.error(f"ALERTA WHATSAPP: Error general inesperado al enviar mensaje: {e}", exc_info=True) # exc_info para traceback
        return False

# --- Helper Functions (Database Interactions) ---
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Rutas de la Aplicación Web (Endpoints) ---
@app.context_processor
def inject_now():
    return {'now': datetime.now(timezone.utc)}

@app.route('/')
def index():
    db = next(get_db_session())
    definiciones_tareas = db.query(TareaDefinicionDB.nombre_tarea).distinct().order_by(TareaDefinicionDB.nombre_tarea).all()
    nombres_tareas_existentes = [t[0] for t in definiciones_tareas]
    return render_template('index.html', nombres_tareas_existentes=nombres_tareas_existentes)

@app.route('/registrar_tarea', methods=['POST'])
def registrar_tarea_route():
    db = next(get_db_session())
    
    empleado_nombre = request.form.get('empleado_nombre', '').strip()
    nombre_tarea = request.form.get('nombre_tarea', '').strip()
    tiempo_estipulado_base_str = request.form.get('tiempo_estipulado_base', '').strip()
    tiempo_real_str = request.form.get('tiempo_real_empleado', '').strip()

    if not empleado_nombre or not nombre_tarea or not tiempo_real_str:
        flash('Nombre del Empleado, Nombre de Tarea y Tiempo Real son obligatorios.', 'error')
        return redirect(url_for('index'))
    try:
        tiempo_real_empleado_float = float(tiempo_real_str)
        if tiempo_real_empleado_float <= 0:
            flash('El Tiempo Real debe ser un número positivo.', 'error')
            return redirect(url_for('index'))
    except ValueError:
        flash('Tiempo Real inválido. Debe ser un número.', 'error')
        return redirect(url_for('index'))

    empleado_obj = db.query(EmpleadoDB).filter(EmpleadoDB.nombre == empleado_nombre).first()
    if not empleado_obj:
        empleado_obj = EmpleadoDB(nombre=empleado_nombre)
        db.add(empleado_obj)
        db.flush() 

    tarea_definicion_obj = db.query(TareaDefinicionDB).filter(TareaDefinicionDB.nombre_tarea == nombre_tarea).first()
    if tiempo_estipulado_base_str:
        try:
            val = float(tiempo_estipulado_base_str)
            if val > 0:
                if tarea_definicion_obj:
                    tarea_definicion_obj.tiempo_estipulado_base = val
                else:
                    tarea_definicion_obj = TareaDefinicionDB(nombre_tarea=nombre_tarea, tiempo_estipulado_base=val)
                    db.add(tarea_definicion_obj)
                db.flush() 
            else:
                flash('El Tiempo Estipulado Base para el tipo de tarea debe ser positivo si se proporciona.', 'error')
                return redirect(url_for('index'))
        except ValueError:
            flash('Tiempo Estipulado Base para el tipo de tarea inválido.', 'error')
            return redirect(url_for('index'))
    
    if not tarea_definicion_obj or tarea_definicion_obj.tiempo_estipulado_base is None:
        flash(f"Error: La tarea '{nombre_tarea}' es nueva o no tiene un tiempo estipulado base. "
              f"Por favor, ingréselo en 'Tiempo Estipulado para este TIPO de Tarea'.", "error")
        return redirect(url_for('index'))
    
    if not empleado_obj.id or not tarea_definicion_obj.id: # Doble chequeo post-flush
        flash("Error crítico: IDs para empleado o definición de tarea no disponibles después de flush.", "error")
        app_logger.error(f"Post-flush ID empleado: {empleado_obj.id}, ID def. tarea: {tarea_definicion_obj.id}")
        db.rollback()
        return redirect(url_for('index'))

    tiempo_estipulado_snapshot_para_registro = tarea_definicion_obj.tiempo_estipulado_base
    fecha_actual_registro = datetime.now(timezone.utc)

    nuevo_registro = RegistroTareaDB(
        empleado_id=empleado_obj.id,
        tarea_definicion_id=tarea_definicion_obj.id,
        tiempo_real_empleado=tiempo_real_empleado_float,
        tiempo_estipulado_snapshot=tiempo_estipulado_snapshot_para_registro,
        fecha_registro=fecha_actual_registro
    )
    db.add(nuevo_registro)
    
    try:
        db.commit()
        flash('✅ Tarea registrada exitosamente.', 'success')

        if tiempo_estipulado_snapshot_para_registro > 0:
            porcentaje_desviacion = ((tiempo_real_empleado_float - tiempo_estipulado_snapshot_para_registro) / tiempo_estipulado_snapshot_para_registro) * 100
            app_logger.info(f"Tarea '{nombre_tarea}' por '{empleado_nombre}': T.Real={tiempo_real_empleado_float}, T.Est.Snap={tiempo_estipulado_snapshot_para_registro}, Desv={porcentaje_desviacion:.2f}%")
            if porcentaje_desviacion > UMBRAL_SOBRETIEMPO_CRITICO_PORCENTAJE:
                app_logger.info(f"Desviación ({porcentaje_desviacion:.2f}%) supera umbral ({UMBRAL_SOBRETIEMPO_CRITICO_PORCENTAJE}%). Intentando enviar alerta.")
                mensaje_alerta = (
                    f"🚨 ALERTA DE SOBRETIEMPO CRÍTICO 🚨\n\n"
                    f"Empleado: {empleado_nombre}\n"
                    f"Tarea: {nombre_tarea}\n"
                    f"Tiempo Real: {tiempo_real_empleado_float:.2f} min\n"
                    f"Tiempo Estipulado: {tiempo_estipulado_snapshot_para_registro:.2f} min\n"
                    f"Desviación: +{porcentaje_desviacion:.2f}% (Umbral: >{UMBRAL_SOBRETIEMPO_CRITICO_PORCENTAJE}%)\n"
                    f"Fecha: {fecha_actual_registro.strftime('%Y-%m-%d %H:%M %Z')}"
                )
                if enviar_alerta_whatsapp_productividad(mensaje_alerta):
                    flash(f"ℹ️ Alerta de sobretiempo crítico enviada por WhatsApp.", "info")
                else:
                    flash(f"⚠️ No se pudo enviar la alerta de sobretiempo por WhatsApp. Revise la configuración y logs de Twilio.", "warning")
            else:
                app_logger.info(f"Desviación ({porcentaje_desviacion:.2f}%) NO supera umbral ({UMBRAL_SOBRETIEMPO_CRITICO_PORCENTAJE}%). No se envía alerta.")

    except Exception as e:
        db.rollback()
        app_logger.error(f"Error al guardar tarea en BD: {e}", exc_info=True)
        flash(f'Error al guardar la tarea. Consulte los logs.', 'error')
        
    return redirect(url_for('index'))

@app.route('/api/timeline_data')
def timeline_data():
    db = next(get_db_session())
    registros = db.query(RegistroTareaDB).order_by(RegistroTareaDB.fecha_registro).all()
    
    items = []
    groups = []
    empleado_ids_in_timeline = set()

    for reg in registros:
        start_time = reg.fecha_registro
        end_time = start_time + timedelta(minutes=reg.tiempo_real_empleado)
        
        diferencia = reg.tiempo_real_empleado - reg.tiempo_estipulado_snapshot
        clase_css_item = "timeline-item-normal"
        if reg.tiempo_estipulado_snapshot > 0:
            porcentaje_desviacion = (diferencia / reg.tiempo_estipulado_snapshot) * 100
            if porcentaje_desviacion > UMBRAL_SOBRETIEMPO_CRITICO_PORCENTAJE:
                clase_css_item = "timeline-item-sobretiempo-critico"
            elif diferencia > 0:
                clase_css_item = "timeline-item-sobretiempo-leve"
            elif diferencia < 0:
                clase_css_item = "timeline-item-temprano"


        tooltip_title = (
            f"<div style='font-family: Inter, sans-serif; font-size: 0.85rem; padding: 5px;'>"
            f"<b>Empleado:</b> {reg.empleado_rel.nombre}<br>"
            f"<b>Tarea:</b> {reg.tarea_definicion_rel.nombre_tarea}<br>"
            f"<hr style='margin: 4px 0;'>"
            f"<b>Inicio:</b> {start_time.strftime('%d/%m/%y %H:%M')}<br>"
            f"<b>Fin:</b> {end_time.strftime('%d/%m/%y %H:%M')}<br>"
            f"<b>T. Real:</b> {reg.tiempo_real_empleado:.1f} min<br>"
            f"<b>T. Estipulado:</b> {reg.tiempo_estipulado_snapshot:.1f} min<br>"
            f"<b>Diferencia:</b> <span style='font-weight: bold; color: {"red" if diferencia > 0 else "green" if diferencia < 0 else "grey"};'>{diferencia:+.1f} min</span>"
            f"</div>"
        )

        items.append({
            "id": reg.id,
            "group": reg.empleado_rel.id,
            "content": f"{reg.tarea_definicion_rel.nombre_tarea} ({reg.tiempo_real_empleado:.0f}m)", # Contenido más conciso
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "title": tooltip_title,
            "type": "range",
            "className": clase_css_item # Clase CSS para estilizar
        })
        
        if reg.empleado_rel.id not in empleado_ids_in_timeline:
            groups.append({
                "id": reg.empleado_rel.id,
                "content": reg.empleado_rel.nombre # Nombre del empleado para el carril
            })
            empleado_ids_in_timeline.add(reg.empleado_rel.id)
            
    return jsonify({"items": items, "groups": groups})


@app.route('/descargar_informe_pdf')
def descargar_informe_pdf_route():
    db = next(get_db_session())
    try:
        # Cargar explícitamente las relaciones para evitar N+1 queries en la plantilla del PDF
        registros = db.query(RegistroTareaDB).options(
            relationship(RegistroTareaDB.empleado_rel), # SQLAlchemy < 2.0 style
            relationship(RegistroTareaDB.tarea_definicion_rel) # SQLAlchemy < 2.0 style
            # Para SQLAlchemy 2.0+ sería: joinedload(RegistroTareaDB.empleado_rel), joinedload(RegistroTareaDB.tarea_definicion_rel)
        ).order_by(EmpleadoDB.nombre, RegistroTareaDB.fecha_registro).all()

        buffer = io.BytesIO()
        # Usar landscape para más espacio horizontal
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), 
                                rightMargin=0.5*inch, leftMargin=0.5*inch, 
                                topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story = []

        style_titulo = ParagraphStyle('TituloPrincipal', parent=styles['h1'], alignment=TA_CENTER, fontSize=16, spaceBefore=0.1*inch, spaceAfter=0.2*inch)
        story.append(Paragraph("Informe Detallado de Tareas Registradas", style_titulo))
        
        fecha_generacion_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
        style_fecha = ParagraphStyle('FechaGeneracion', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=9, spaceAfter=0.2*inch)
        story.append(Paragraph(f"Generado el: {fecha_generacion_str}", style_fecha))

        if not registros:
            story.append(Paragraph("No hay tareas registradas para mostrar en el informe.", styles['Normal']))
        else:
            data_table = [
                [Paragraph("<b>Fecha Registro</b>", styles['Normal']), 
                 Paragraph("<b>Empleado</b>", styles['Normal']), 
                 Paragraph("<b>Tarea</b>", styles['Normal']), 
                 Paragraph("<b>T. Estipulado (min)</b>", styles['Normal']), 
                 Paragraph("<b>T. Real (min)</b>", styles['Normal']), 
                 Paragraph("<b>Diferencia (min)</b>", styles['Normal'])]
            ]
            
            for reg in registros:
                # Asegurarse que las relaciones estén cargadas
                empleado_nombre_pdf = reg.empleado_rel.nombre if reg.empleado_rel else "N/A"
                tarea_nombre_pdf = reg.tarea_definicion_rel.nombre_tarea if reg.tarea_definicion_rel else "N/A"
                diferencia = reg.tiempo_real_empleado - reg.tiempo_estipulado_snapshot
                
                data_table.append([
                    Paragraph(reg.fecha_registro.strftime('%Y-%m-%d %H:%M'), styles['Normal']),
                    Paragraph(empleado_nombre_pdf, styles['Normal']),
                    Paragraph(tarea_nombre_pdf, styles['Normal']),
                    Paragraph(f"{reg.tiempo_estipulado_snapshot:.2f}", styles['Normal']),
                    Paragraph(f"{reg.tiempo_real_empleado:.2f}", styles['Normal']),
                    Paragraph(f"{diferencia:+.2f}", styles['Normal'])
                ])

            table = Table(data_table, colWidths=[1.6*inch, 2.2*inch, 2.7*inch, 1.2*inch, 1.2*inch, 1.1*inch]) # Ajustar anchos
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkslategray), # Encabezado más oscuro
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'), # Alinear a la izquierda para mejor lectura
                ('ALIGN', (3, 1), (-1, -1), 'RIGHT'), # Alinear números a la derecha
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9), # Tamaño de fuente un poco más pequeño para caber
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10), # Padding
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.ghostwhite), # Fondo de filas alterno podría ser una opción
                ('GRID', (0, 0), (-1, -1), 0.5, colors.silver), # Grid más sutil
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 4), # Padding interno de celdas
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(table)

        doc.build(story)
        buffer.seek(0)
        
        filename = f"informe_tareas_detallado_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        app_logger.info(f"Generando PDF: {filename}")
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

    except Exception as e:
        app_logger.error(f"Error al generar PDF: {e}", exc_info=True)
        flash("Error al generar el informe PDF. Consulte los logs del servidor.", "error")
        return redirect(url_for('index')) # Redirigir a index en caso de error


@app.route('/limpiar_todo_timeline', methods=['POST'])
def limpiar_todo_timeline_route():
    db = next(get_db_session())
    try:
        num_registros = db.query(RegistroTareaDB).delete()
        num_defs_tareas = db.query(TareaDefinicionDB).delete()
        num_empleados = db.query(EmpleadoDB).delete()
        db.commit()
        flash(f'¡DATOS ELIMINADOS! {num_registros} registros, {num_defs_tareas} definiciones de tareas y {num_empleados} empleados fueron borrados.', 'warning')
    except Exception as e:
        db.rollback()
        app_logger.error(f"Error al limpiar toda la base de datos de timeline: {e}", exc_info=True)
        flash(f'Error al limpiar la base de datos. Consulte logs.', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app_logger.info("Iniciando aplicación de Gestión de Tareas con Línea de Tiempo.")
    if not twilio_configured_properly:
        app_logger.warning("ADVERTENCIA: Credenciales de Twilio no configuradas o incorrectas. Alertas WhatsApp no funcionarán.")
    elif not twilio_client:
         app_logger.error("ERROR: El cliente de Twilio no se pudo inicializar a pesar de tener credenciales. Verifique su validez.")
        
    port = int(os.environ.get('FLASK_RUN_PORT', 5005)) # Puerto diferente para esta versión
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    app_logger.info(f"Aplicación corriendo en http://127.0.0.1:{port}")
    if debug_mode: app_logger.info("Modo DEBUG de Flask ACTIVADO.")
    
    app.run(debug=debug_mode, port=port, host='0.0.0.0')