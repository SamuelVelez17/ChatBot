import requests
import json
import time
from datetime import datetime
import db
import threading
import logging
from dotenv import load_dotenv
import os

# Configuración básica de logging
logging.basicConfig(filename='services.log', level=logging.DEBUG)
load_dotenv()

# Diccionario global para almacenar los tiempos de los usuarios
user_timers = {}
INACTIVITY_TIME_LIMIT = 120  # 2 minutos de inactividad

# Lock para manejar el estado de manera segura en un entorno multi-hilo
estado_lock = threading.Lock()

# Función para enviar mensaje de texto a través de WhatsApp
def enviar_Mensaje_whatsapp(data):
    try:
        whatsapp_token = os.getenv("whatsapp_token")
        whatsapp_url = os.getenv("whatsapp_url")
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + whatsapp_token}
        logging.info("Enviando mensaje de WhatsApp.")
        response = requests.post(whatsapp_url, headers=headers, data=data)
        
        if response.status_code == 200:
            logging.info("Mensaje enviado exitosamente.")
            return 'mensaje enviado', 200
        else:
            logging.error(f"Error al enviar mensaje: {response.status_code} - {response.text}")
            return 'error al enviar mensaje', response.status_code
    except Exception as e:
        logging.error(f"Error al intentar enviar el mensaje: {e}")
        return str(e), 403

# Función para generar un mensaje de texto
def text_Message(number, text):
    data = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": number,
        "type": "text",
        "text": {
            "body": text
        }
    })
    logging.info(f"Mensaje de texto generado para el número {number}.")
    return data

# Función que reinicia el temporizador de inactividad
def check_inactivity():
    while True:
        try:
            conn = db.conectar()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT numero, estado, ultima_actividad FROM BOT_estado_usuario")
                usuarios = cursor.fetchall()
                ahora = datetime.now()
                for usuario in usuarios:
                    # Ignorar a los usuarios en estado "inicio"
                    if usuario.estado == "inicio":
                        continue
                    
                    tiempo_inactivo = (ahora - usuario.ultima_actividad).total_seconds()
                    if tiempo_inactivo > INACTIVITY_TIME_LIMIT:
                        # Verificar si el usuario aún existe en la base de datos
                        estado_actual = db.obtener_estado(usuario.numero)
                        if estado_actual:  # Si el usuario aún existe, proceder con la desconexión
                            # Eliminar al usuario de la base de datos antes de enviar el mensaje
                            db.eliminar_usuario(usuario.numero)
                            logging.info(f"Usuario {usuario.numero} eliminado por inactividad.")
                            
                            # Enviar mensaje de desconexión
                            mensaje_desconexion = "⏱ Has sido desconectado por inactividad."
                            enviar_Mensaje_whatsapp(text_Message(usuario.numero, mensaje_desconexion))
                            
                            # Eliminar el temporizador de inactividad del usuario
                            if usuario.numero in user_timers:
                                del user_timers[usuario.numero]
                conn.close()
        except Exception as e:
            logging.error(f"Error en check_inactivity: {e}")
        finally:
            time.sleep(60)  # Esperar 60 segundos antes de la siguiente verificación
            
def reset_inactivity_timer(number):
    estado_actual = db.obtener_estado(number)
    if estado_actual:
        db.actualizar_estado(number, estado_actual["estado"], estado_actual.get("paso"))
    else:
        db.insertar_usuario(number, "inicio")
    
    # Reiniciar el temporizador de inactividad
    user_timers[number] = time.time()
        
def start_inactivity_check():   
    thread = threading.Thread(target=check_inactivity, daemon=True)
    thread.start()

# Función que obtiene el mensaje de WhatsApp
def obtener_Mensaje_whatsapp(message):
    if 'type' not in message:
        return 'mensaje no reconocido'

    typeMessage = message['type']
    if typeMessage == 'text':
        return message['text']['body']
    elif typeMessage == 'button':
        return message['button']['text']
    elif typeMessage == 'interactive' and message['interactive']['type'] == 'list_reply':
        return message['interactive']['list_reply']['title']
    elif typeMessage == 'interactive' and message['interactive']['type'] == 'button_reply':
        return message['interactive']['button_reply']['title']
    else:
        logging.warning(f"Mensaje no procesado correctamente, tipo: {typeMessage}")
        return 'mensaje no procesado'

# Función para generar un mensaje con botones de respuesta
def buttonReply_Message(number, options, body, footer, sedd, messageId):
    buttons = [{"type": "reply", "reply": {"id": f"{sedd}_btn_{i+1}", "title": option}} for i, option in enumerate(options)]
    data = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "footer": {"text": footer},
            "action": {"buttons": buttons}
        }
    })
    logging.info(f"Opciones de botón generadas para el número {number}.")
    return data

# Función para generar un mensaje con lista de opciones
def listReply_Message(number, opciones, body, footer, sedd, messageId):
    rows = [{"id": f"{sedd}_opt_{id_opcion}", "title": nombre_opcion} for id_opcion, nombre_opcion in opciones.items()]
    data = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": body},
            "body": {"text": footer},
            "action": {
                "button": "Ver opciones",
                "sections": [{"title": "Opciones de soporte", "rows": rows}]
            }
        }
    })
    logging.info(f"Opciones de lista generadas para el número {number}.")
    return data

# Función principal para administrar el chatbot
def administrar_chatbot(text, number, messageId, name):
    with estado_lock:
        try:
            estado_actual = db.obtener_estado(number) or {"estado": "inicio"}
            
            if text.strip().lower() in ["fin", "finalizar"]:
                enviar_Mensaje_whatsapp(text_Message(number, "👋 ¡Gracias por usar nuestro servicio!"))
                
                # Limpiar TODOS los datos del usuario
                db.actualizar_estado(
                    number, 
                    "inicio", 
                    paso=None, 
                    tienda_id=None, 
                    nombre_usuario=None  # Asegurar que el nombre se borre
                )
                
                # Alternativa: También puedes usar eliminar_usuario si prefieres
                # db.eliminar_usuario(number)
                
                if number in user_timers:
                    del user_timers[number]
                return

            # Definición de opciones de soporte y áreas
            opciones_soporte = {
                "43": "Factura Mayor",
                "59": "Generar JSON Hiopos>KF",
                "60": "Restaurar Backup KF",
                "44": "Borrar Hist Ventas HData",
                "41": "Gestionar Códigos Null",
                "42": "Borrado de Precios",
                "38": "Otro"
            }
            areas = {
                "1": "Captura",
                "2": "Negocios/Consultoría",
                "3": "Administración",
                "4": "TI"
            }

            # Funciones de estado
            def estado_inicio():
                saludos = ["hola", "buenas", "buenos", "compa", "soporte", "ti", "ayuda", "necesito", "tienda", "id", "buen"]
                if any(saludo in text.lower() for saludo in saludos):
                    # 1. Primero actualizar el estado en la base de datos
                    if not db.actualizar_estado(number, "esperando_confirmacion"):
                        logging.error(f"No se pudo actualizar estado para {number}")
                        enviar_Mensaje_whatsapp(text_Message(number, "⚠️ Error temporal. Por favor intenta nuevamente."))
                        return
                        
                    # 2. Preparar y enviar mensajes solo si el estado se guardó correctamente
                    mensaje = "📩 ¡Bienvenido al chat de soporte TI de Tienda Registrada! ¿Cómo podemos ayudarte hoy?"
                    botones = ["Crear solicitud", "Consultar solicitud"]
                    recordatorio = "⏰ Finalizaremos automáticamente el chat después de 2 minutos de inactividad. Para finalizar el chat antes escriba 'Fin' o 'Finalizar'."
                    
                    # Enviar mensajes
                    enviar_Mensaje_whatsapp(text_Message(number, recordatorio))
                    data = buttonReply_Message(number, botones, mensaje, "Selecciona una opción", "confirmacion", messageId)
                    enviar_Mensaje_whatsapp(data)
                    
                    # 3. Inicializar temporizador
                    if number not in user_timers:
                        user_timers[number] = time.time()
                else:
                    mensaje = "👋🏽 Por favor, saluda antes de iniciar."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_confirmacion():
                texto_normalizado = text.strip().lower()
                if texto_normalizado == "crear solicitud":
                    mensaje = "¿A qué área perteneces?"
                    data = listReply_Message(number, areas, mensaje, "Selecciona una opción", "confirmacion", messageId)
                    enviar_Mensaje_whatsapp(data)
                    db.actualizar_estado(number, "esperando_seleccion_area")
                elif texto_normalizado == "consultar solicitud":
                    mensaje = "¿Cuál es el número del ticket a consultar?"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "esperando_ticket")
                else:
                    mensaje = "Por favor, selecciona una opción. 😊"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_ticket():
                if text.isdigit():
                    ticket_id = text
                    mensaje = "💬 Estamos buscando información relacionada con el número de ticket que nos proporcionaste. ¡En un momento regresamos contigo!"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    ticket = db.consultarTicketConUsuario(ticket_id)
                    if ticket:
                        if isinstance(ticket, dict):
                            numero_ticket = ticket.get('id', 'Ticket desconocido')
                            responsable = ticket.get('users_id_recipient', 'Usuario desconocido')
                            asignado = ticket.get('users_id_lastupdater', 'SIN ASIGNAR')
                            estado = ticket.get('status', 'SIN REVISAR')
                            if estado == "Nuevo":
                                mensaje_estado = "🏃🏽‍♂️En breve, un miembro de nuestro equipo comenzará a trabajar en tu solicitud. Te enviaremos todas las actualizaciones del caso al correo electrónico registrado."
                                enviar_Mensaje_whatsapp(text_Message(number, mensaje_estado))
                            else:
                                # Guardamos el ticket en la base de datos
                                db.actualizar_estado(number, estado_actual["estado"], paso=json.dumps({
                                    "ticket_id": numero_ticket,
                                    "responsable": responsable,
                                    "asignado": asignado,
                                    "estado": estado
                                }))
                                
                                mensaje = f"El ticket *#{numero_ticket}* 🎫, creado por *{responsable}* 🙋🏻, fue asignado a *{asignado}* y se encuentra en estado *{estado}*."
                                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                            mensaje2 = "🥹 Hemos finalizado tu chat, hasta pronto."
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje2))
                            db.actualizar_estado(number, "inicio")
                            if number in user_timers:
                                del user_timers[number]
                        else:
                            logging.error(f"Error al consultar el ticket: {ticket}")
                            mensaje = "Error al consultar el ticket."
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    else:
                        mensaje = "No hemos encontrado un ticket con ese ID ❌. Verifica el ID y envíalo nuevamente."
                        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                else:
                    mensaje = "Envía un ID de ticket válido, un número."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_seleccion_area():
                texto_normalizado = text.strip().lower()
                if texto_normalizado in ["negocios/consultoría", "administración", "ti"]:
                    db.actualizar_estado(number, "inicio_oficina")
                    mensaje = "👤 A continuación, ingresa tu nombre completo."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "esperando_nombre")
                elif texto_normalizado == "captura":
                    db.actualizar_estado(number, "inicio_captura")
                    mensaje = "✍🏽 Ingresa el ID del establecimiento para el que necesitas el soporte."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "esperando_id")
                else:
                    mensaje = "Por favor selecciona una opción válida. 😊"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_nombre():
                nombre = text.strip()
                # Guardamos el nombre en la columna nombre_usuario Y en paso para compatibilidad
                db.actualizar_estado(
                    number, 
                    "esperando_confirmacion_nombre", 
                    nombre_usuario=nombre,
                    paso=nombre  # Doble almacenamiento por seguridad
                )
                
                mensaje = f"📝 Ingresaste tu nombre como *{nombre}*, ¿Es correcto?"
                data = buttonReply_Message(number, ["Sí", "No"], mensaje, "Confirma tu selección", "confirmacion", messageId)
                enviar_Mensaje_whatsapp(data)

            def estado_esperando_confirmacion_nombre():
                texto_normalizado = text.strip().lower()
                estado_actual = db.obtener_estado(number)
                
                # Recuperamos el nombre de ambas columnas por seguridad
                nombre = estado_actual.get("nombre_usuario") or estado_actual.get("paso") if estado_actual else None
                
                if not nombre:
                    mensaje = "No se encontró tu nombre. Por favor, inicia el proceso nuevamente."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "inicio")
                    return
                
                if texto_normalizado in ["sí", "si"]:
                    # Pasamos el nombre al siguiente estado explícitamente
                    db.actualizar_estado(
                        number, 
                        "esperando_descripcion_oficina", 
                        nombre_usuario=nombre,  # Mantenemos el nombre
                        paso="confirmado"  # Marcamos confirmación
                    )
                    mensaje = "✉️ Describe tu solicitud, para que nuestro equipo de soporte pueda ayudarte."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                elif texto_normalizado == "no":
                    mensaje = "🖌️ Envía tu nombre completo de nuevo, por favor."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "esperando_nombre")
                else:
                    mensaje = "Por favor confirma con 'Sí' ✅ o 'No' ❌."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_descripcion_oficina():
                descripcion = text.strip()
                estado_actual = db.obtener_estado(number)
                
                nombre = estado_actual.get("nombre_usuario") if estado_actual else None
                
                if not nombre:
                    mensaje = "❌ No se encontró tu nombre. Por favor, inicia el proceso nuevamente."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "inicio", nombre_usuario=None)
                    return
                
                # Guardar la descripción en la base de datos antes de crear el ticket
                db.actualizar_estado(
                    number,
                    estado_actual["estado"],
                    paso=descripcion,  # Almacenamos la descripción en 'paso'
                    nombre_usuario=nombre
                )
                
                respuesta = db.crearTicketYAsignarUsuario(
                    nombre_tienda="Oficina",
                    responsable=nombre,
                    estado="Nuevo",
                    opcion_id=38,
                    descripcion=f"Soporte solicitado por: {nombre}. {descripcion}",
                    tienda_id=None
                )
                
                # Limpiar datos después de crear ticket
                db.actualizar_estado(
                    number, 
                    "inicio", 
                    paso=None, 
                    tienda_id=None, 
                    nombre_usuario=None
                )
                
                if "error" in respuesta:
                    mensaje_error = f"Hubo un error al procesar tu solicitud: {respuesta['error']}"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje_error))
                else:
                    mensaje_exito = f"{respuesta['message']}"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje_exito))
                    enviar_Mensaje_whatsapp(text_Message(number, "🥹 Hemos finalizado tu chat, hasta pronto."))
                    if number in user_timers:
                        del user_timers[number]

            def estado_esperando_id():
                if text.isdigit():
                    tienda_id = text
                    mensaje = "💬 Estamos buscando información relacionada con el ID que nos proporcionaste. ¡En un momento regresamos contigo!"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    tienda = db.verificarTienda(tienda_id)
                    if tienda:
                        nombre_tienda = tienda.get('NombreTienda', 'Tienda desconocida')
                        responsable = tienda.get('ResponsableDeTienda', 'Responsable desconocido')
                        estado = tienda.get('Estado', 'Estado desconocido')
                        
                        # Guardamos los datos de la tienda en la base de datos
                        db.actualizar_estado(number, "esperando_confirmacion_tienda", tienda_id=tienda_id)
                        
                        mensaje = f"❗Has seleccionado 🏪 *{nombre_tienda}*, cuyo responsable es 🙋🏻 *{responsable}* y que se encuentra en estado *{estado}* al día de hoy. ¿Es correcto? 🤔"
                        data = buttonReply_Message(number, ["Sí", "No"], mensaje, "Confirma tu selección", "confirmacion", messageId)
                        enviar_Mensaje_whatsapp(data)
                    else:
                        mensaje = "No hemos encontrado una tienda con ese ID ❌. Verifica el id y envíalo nuevamente."
                        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                else:
                    mensaje = "Por favor, envía un ID de tienda válido (un número). 😊"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_confirmacion_tienda():
                texto_normalizado = text.strip().lower()
                estado_actual = db.obtener_estado(number)
                
                if not estado_actual or 'tienda_id' not in estado_actual:
                    mensaje = "❌ Error: No se encontró información de la tienda. Por favor, inicia el proceso nuevamente."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "inicio")
                    return
                
                tienda_id = estado_actual['tienda_id']
                
                if texto_normalizado in ["sí", "si"]:
                    # Verificar nuevamente la tienda antes de continuar
                    tienda = db.verificarTienda(tienda_id)
                    if not tienda:
                        mensaje = "❌ La tienda ya no está disponible. Por favor, inicia el proceso nuevamente."
                        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                        db.actualizar_estado(number, "inicio")
                        return
                        
                    db.actualizar_estado(
                        number, 
                        "esperando_seleccion", 
                        tienda_id=tienda_id,  # Mantener el tienda_id
                        nombre_usuario=estado_actual.get("nombre_usuario")  # Mantener el nombre si existe
                    )
                    mensaje = "Por favor, elige una opción de soporte: 🙌🏻"
                    data = listReply_Message(number, opciones_soporte, mensaje, "Selecciona una opción", "soporte", messageId)
                    enviar_Mensaje_whatsapp(data)
                    
                elif texto_normalizado == "no":
                    mensaje = "Por favor, envíame el ID de la tienda nuevamente. 😊"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "esperando_id")
                else:
                    mensaje = "Por favor confirma con 'Sí' o 'No'."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_seleccion():
                opcion_id = next((key for key, value in opciones_soporte.items() if value.lower() == text.lower()), None)
                estado_actual = db.obtener_estado(number)
                
                if not estado_actual or 'tienda_id' not in estado_actual:
                    mensaje = "❌ Error: No se encontró información de la tienda. Por favor, inicia el proceso nuevamente."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "inicio")
                    return
                
                tienda_id = estado_actual['tienda_id']
                tienda = db.verificarTienda(tienda_id)
                
                if not tienda:
                    mensaje = "❌ La tienda ya no está disponible. Por favor, inicia el proceso nuevamente."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    db.actualizar_estado(number, "inicio")
                    return
                
                if opcion_id:
                    nombre_tienda = tienda.get('NombreTienda', 'Tienda desconocida')
                    responsable = tienda.get('ResponsableDeTienda', 'Responsable desconocido')
                    estado = tienda.get('Estado', 'Estado desconocido')
                    
                    if opcion_id == "38":  # "Otro"
                        mensaje = "✉️ Describe tu solicitud, para que nuestro equipo de soporte pueda ayudarte."
                        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                        db.actualizar_estado(
                            number, 
                            "esperando_descripcion", 
                            tienda_id=tienda_id,
                            nombre_usuario=estado_actual.get("nombre_usuario")
                        )
                    else:
                        respuesta = db.crearTicketYAsignarUsuario(
                            nombre_tienda,
                            responsable,
                            estado,
                            opcion_id,
                            tienda_id=tienda_id
                        )
                        
                        if "error" in respuesta:
                            mensaje_error = f"Error al procesar tu solicitud: {respuesta['error']}"
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje_error))
                        else:
                            mensaje_exito = f"{respuesta['message']}"
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje_exito))
                            enviar_Mensaje_whatsapp(text_Message(number, "🥹 Hemos finalizado tu chat, hasta pronto."))
                            db.actualizar_estado(number, "inicio")
                else:
                    mensaje = "Opción de soporte no válida ❌. Selecciona del menú."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_descripcion():
                descripcion = text.strip()
                estado_actual = db.obtener_estado(number)
                tienda_id = estado_actual.get("tienda_id") if estado_actual else None
                nombre = (estado_actual.get("nombre_usuario") or 
                        estado_actual.get("paso") if estado_actual else "Usuario no identificado")
                
                if not tienda_id:
                    enviar_Mensaje_whatsapp(text_Message(number, "❌ No se encontró información de la tienda. Por favor, inicia el proceso nuevamente."))
                    db.actualizar_estado(number, "inicio")
                    return
                
                tienda = db.verificarTienda(tienda_id)
                if not tienda:
                    enviar_Mensaje_whatsapp(text_Message(number, "❌ No se encontró información de la tienda. Por favor, inicia el proceso nuevamente."))
                    db.actualizar_estado(number, "inicio")
                    return
                
                # Guardar la descripción en la base de datos antes de crear el ticket
                db.actualizar_estado(
                    number,
                    estado_actual["estado"],
                    paso=descripcion,  # Almacenamos la descripción en 'paso'
                    tienda_id=tienda_id,
                    nombre_usuario=nombre
                )
                
                respuesta = db.crearTicketYAsignarUsuario(
                    nombre_tienda=tienda.get('NombreTienda', 'Tienda desconocida'),
                    responsable=tienda.get('ResponsableDeTienda', 'Responsable desconocido'),
                    estado="Nuevo",
                    opcion_id=38,
                    descripcion=f"Soporte solicitado para la tienda: {tienda.get('NombreTienda')}, (ID: {tienda_id}). {descripcion}",
                    tienda_id=tienda_id
                )
                
                if "error" in respuesta:
                    enviar_Mensaje_whatsapp(text_Message(number, f"Error: {respuesta['error']}"))
                else:
                    enviar_Mensaje_whatsapp(text_Message(number, f"{respuesta['message']}"))
                    enviar_Mensaje_whatsapp(text_Message(number, "🥹 Hemos finalizado tu chat, hasta pronto."))
                    db.actualizar_estado(number, "inicio")

            # Mapeo de estados a funciones
            estados_funciones = {
                "inicio": estado_inicio,
                "esperando_confirmacion": estado_esperando_confirmacion,
                "esperando_nombre": estado_esperando_nombre,
                "esperando_confirmacion_nombre": estado_esperando_confirmacion_nombre,
                "esperando_descripcion_oficina": estado_esperando_descripcion_oficina,
                "esperando_id": estado_esperando_id,
                "esperando_confirmacion_tienda": estado_esperando_confirmacion_tienda,
                "esperando_seleccion": estado_esperando_seleccion,
                "esperando_seleccion_area": estado_esperando_seleccion_area,
                "esperando_descripcion": estado_esperando_descripcion,
                "esperando_ticket": estado_esperando_ticket
            }

            # Verificar si el estado actual es válido
            if estado_actual["estado"] not in estados_funciones:
                mensaje = "Ha ocurrido un error. Por favor, inicia el flujo nuevamente. 😊"
                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                db.actualizar_estado(number, "inicio")
                return

            # Ejecutar la función correspondiente al estado actual
            estados_funciones[estado_actual["estado"]]()
        except Exception as e:
            logging.error(f"Error en el flujo del chatbot para el usuario {number}: {e}", exc_info=True)
            mensaje = "Ha ocurrido un error inesperado. Por favor, inicia el flujo nuevamente. 😊"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
            db.actualizar_estado(number, "inicio")

# Iniciar el chequeo de inactividad
start_inactivity_check()
