import requests
import json
import time
import db
import app
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
def reset_inactivity_timer(number):
    current_time = time.time()
    #with estado_lock:  # Adquirir el bloqueo solo cuando sea necesario
    user_timers[number] = current_time
    logging.info(f"Temporizador de usuario {number} reiniciado a {current_time}.")

# Función que verifica la inactividad de los usuarios
def check_inactivity():
    current_time = time.time()
    with estado_lock:  # Adquirir el bloqueo para proteger user_timers
        for number, last_activity_time in list(user_timers.items()):
            if current_time - last_activity_time > INACTIVITY_TIME_LIMIT:
                logging.info(f"Usuario {number} inactivo por más de {INACTIVITY_TIME_LIMIT} segundos.")
                mensaje = "⏱ Has sido desconectado por inactividad. Si necesitas ayuda, vuelve a iniciar el chat."
                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                # Limpiar el estado del usuario
                app.estados.pop(number, None)
                app.estados.pop(f"{number}_nombre", None)
                app.estados.pop(f"{number}_otros", None)
                app.estados.pop(f"{number}_tienda", None)
                del user_timers[number]
            else:
                logging.info(f"Usuario {number} aún activo, tiempo desde última actividad: {current_time - last_activity_time}s")

# Inicia el chequeo de inactividad en un hilo separado
def start_inactivity_check():
    if not hasattr(start_inactivity_check, "thread_started"):  # Verificar si el hilo ya está en ejecución
        def inactivity_check_loop():
            while True:
                check_inactivity()
                time.sleep(60)  # Revisa cada minuto

        inactivity_thread = threading.Thread(target=inactivity_check_loop, daemon=True)
        inactivity_thread.start()
        start_inactivity_check.thread_started = True  # Marcar que el hilo ya está en ejecución

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
    with estado_lock:  # Adquirir el bloqueo al inicio
        try:
            # Verificar si el usuario quiere finalizar el chat
            if text.strip().lower() in ["fin", "finalizar"]:
                mensaje = "👋 ¡Gracias por usar nuestro servicio de soporte! Si necesitas más ayuda, no dudes en volver a iniciar el chat."
                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                # Limpiar el estado del usuario
                app.estados.pop(number, None)
                app.estados.pop(f"{number}_nombre", None)
                app.estados.pop(f"{number}_otros", None)
                app.estados.pop(f"{number}_tienda", None)
                del user_timers[number]
                return  # Finalizar la ejecución del flujo
            
            reset_inactivity_timer(number)  # Reiniciar el temporizador de inactividad
            estado_actual = app.estados.get(number, "inicio")
            logging.info(f"Inicio del flujo de chat para el número {number} con el mensaje: {text}")
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")

            # Definición de opciones de soporte y áreas
            opciones_soporte = {
                "43": "Factura Mayor",
                "59": "Generar JSON Hiopos>KF",
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
                    mensaje = "📩 ¡Bienvenido al chat de soporte TI de Tienda Registrada! ¿Cómo podemos ayudarte hoy?"
                    botones = ["Crear solicitud", "Consultar solicitud"]
                    recordatorio = "⏰ Finalizaremos automáticamente el chat después de 2 minutos de inactividad. Para finalizar el chat antes escriba 'Fin' o 'Finalizar'."
                    enviar_Mensaje_whatsapp(text_Message(number, recordatorio))
                    data = buttonReply_Message(number, botones, mensaje, "Selecciona una opción", "confirmacion", messageId)
                    enviar_Mensaje_whatsapp(data)
                    app.estados[number] = "esperando_confirmacion"  # Actualizar el estado correctamente
                else:
                    mensaje = "👋🏽 Por favor, saluda antes de iniciar."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_confirmacion():
                texto_normalizado = text.strip().lower()
                if texto_normalizado == "crear solicitud":
                    mensaje = "¿A qué área perteneces?"
                    data = listReply_Message(number, areas, mensaje, "Selecciona una opción", "confirmacion", messageId)
                    enviar_Mensaje_whatsapp(data)
                    app.estados[number] = "esperando_seleccion_area"  # Actualizar el estado correctamente
                elif texto_normalizado == "consultar solicitud":
                    mensaje = "¿Cuál es el número del ticket a consultar?"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    app.estados[number] = "esperando_ticket"  # Actualizar el estado correctamente
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
                                app.estados[f"{number}_ticket"] = {
                                    "id": numero_ticket,
                                    "responsable": responsable,
                                    "asignado": asignado,
                                    "estado": estado
                                }
                                mensaje = f"El ticket *#{numero_ticket}* 🎫, creado por *{responsable}* 🙋🏻, fue asignado a *{asignado}* y se encuentra en estado *{estado}*."
                                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                            mensaje2 = "🥹 Hemos finalizado tu chat, hasta pronto."
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje2))
                            app.estados[number] = "inicio"
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
                    app.estados[number] = "inicio_oficina"
                    mensaje = "👤 A continuación, ingresa tu nombre completo."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    app.estados[number] = "esperando_nombre"
                elif texto_normalizado == "captura":
                    app.estados[number] = "inicio_captura"
                    mensaje = "✍🏽 Ingresa el ID del establecimiento para el que necesitas el soporte."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    app.estados[number] = "esperando_id"
                else:
                    mensaje = "Por favor selecciona una opción válida. 😊"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_nombre():
                nombre = text.strip()
                app.estados[f"{number}_nombre"] = nombre
                mensaje = f"📝 Ingresaste tu nombre como *{nombre}*, ¿Es correcto?"
                data = buttonReply_Message(number, ["Sí", "No"], mensaje, "Confirma tu selección", "confirmacion", messageId)
                enviar_Mensaje_whatsapp(data)
                app.estados[number] = "esperando_confirmacion_nombre"

            def estado_esperando_confirmacion_nombre():
                texto_normalizado = text.strip().lower()
                if texto_normalizado in ["sí", "si"]:
                    mensaje = "✉️ Describe tu solicitud, para que nuestro equipo de soporte pueda ayudarte."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    app.estados[number] = "esperando_descripcion_oficina"
                elif texto_normalizado == "no":
                    mensaje = "🖌️ Envía tu nombre completo de nuevo, por favor."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    app.estados[number] = "esperando_nombre"
                else:
                    mensaje = "Por favor confirma con 'Sí' ✅ o 'No' ❌."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_descripcion_oficina():
                descripcion = text.strip()
                nombre = app.estados.get(f"{number}_nombre", "Usuario desconocido")
                respuesta = db.crearTicketYAsignarUsuario(
                    nombre_tienda="Oficina",
                    responsable=nombre,
                    estado="Nuevo",
                    opcion_id=38,
                    descripcion=f"Soporte solicitado por: {nombre}. {descripcion}"
                )
                if "error" in respuesta:
                    mensaje_error = f"Hubo un error al procesar tu solicitud: {respuesta['error']}"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje_error))
                else:
                    mensaje_exito = f"{respuesta['message']}"
                    mensaje = "🥹 Hemos finalizado tu chat, hasta pronto."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje_exito))
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                app.estados.pop(number, None)
                app.estados.pop(f"{number}_nombre", None)
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
                        # Almacenar el ID de la tienda en el estado del usuario
                        app.estados[f"{number}_tienda"] = {"id": tienda_id, "nombre": nombre_tienda, "responsable": responsable, "estado": estado}
                        mensaje = f"❗Has seleccionado 🏪 *{nombre_tienda}*, cuyo responsable es 🙋🏻 *{responsable}* y que se encuentra en estado *{estado}* al día de hoy. ¿Es correcto? 🤔"
                        data = buttonReply_Message(number, ["Sí", "No"], mensaje, "Confirma tu selección", "confirmacion", messageId)
                        enviar_Mensaje_whatsapp(data)
                        app.estados[number] = "esperando_confirmacion_tienda"
                    else:
                        mensaje = "No hemos encontrado una tienda con ese ID ❌. Verifica el id y envíalo nuevamente."
                        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                else:
                    mensaje = "Por favor, envía un ID de tienda válido (un número). 😊"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_confirmacion_tienda():
                texto_normalizado = text.strip().lower()
                if texto_normalizado in ["sí", "si"]:
                    app.estados[number] = "esperando_seleccion"
                    mensaje = "Por favor, elige una opción de soporte: 🙌🏻"
                    data = listReply_Message(number, opciones_soporte, mensaje, "Selecciona una opción", "soporte", messageId)
                    enviar_Mensaje_whatsapp(data)
                elif texto_normalizado == "no":
                    mensaje = "Por favor, envíame el ID de la tienda nuevamente. 😊"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    app.estados[number] = "esperando_id"
                else:
                    mensaje = "Por favor confirma con 'Sí' o 'No'."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_seleccion():
                opcion_id = next((key for key, value in opciones_soporte.items() if value.lower() == text.lower()), None)
                if opcion_id:
                    logging.info(f"Estado actual del usuario {number}: {estado_actual}")
                    tienda = app.estados.get(f"{number}_tienda", {"nombre": "Tienda desconocida", "responsable": "Responsable desconocido", "estado": "Estado desconocido"})
                    nombre_tienda = tienda["nombre"]
                    responsable = tienda["responsable"]
                    tienda_id = tienda.get("id")  # Obtener el ID de la tienda
                    if opcion_id == "38":  # "Otro"
                        mensaje = "✉️ Describe tu solicitud, para que nuestro equipo de soporte pueda ayudarte."
                        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                        app.estados[number] = "esperando_descripcion"
                        app.estados[f"{number}_otros"] = {"nombre_tienda": nombre_tienda, "responsable": responsable, "opcion_id": opcion_id, "estado": tienda.get("estado"), "tienda_id": tienda_id}  # Incluir el ID de la tienda
                    else:  # Opción específica (Factura Mayor, etc.)
                        respuesta = db.crearTicketYAsignarUsuario(nombre_tienda, responsable, tienda.get("estado"), opcion_id, tienda_id=tienda_id)  # Pasar el ID de la tienda
                        if "error" in respuesta:
                            mensaje_error = f"Error al procesar tu solicitud: {respuesta['error']}"
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje_error))
                        else:
                            mensaje_exito = f"{respuesta['message']}"
                            mensaje = "🥹Hemos finalizado tu chat, hasta pronto."
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje_exito))
                            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                            del user_timers[number]
                            app.estados[number] = "inicio"
                else:
                    mensaje = "Opción de soporte no válida ❌. Selecciona del menú."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))

            def estado_esperando_descripcion():
                otros_datos = app.estados.get(f"{number}_otros", {})
                nombre_tienda = otros_datos.get("nombre_tienda", "Tienda desconocida")
                responsable = otros_datos.get("responsable", "Responsable desconocido")
                estado = otros_datos.get("estado", "Estado desconocido")
                opcion_id = otros_datos.get("opcion_id", "38")
                tienda_id = otros_datos.get("tienda_id")  # Obtener el ID de la tienda
                descripcion = text.strip()
                respuesta = db.crearTicketYAsignarUsuario(nombre_tienda, responsable, estado, opcion_id, descripcion, tienda_id=tienda_id)  # Pasar el ID de la tienda
                if "error" in respuesta:
                    mensaje_error = f"Error al procesar tu solicitud: {respuesta['error']}"
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje_error))
                else:
                    mensaje_exito = f"{respuesta['message']}"
                    mensaje = "🥹 Hemos finalizado tu chat, hasta pronto."
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje_exito))
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                    del user_timers[number]
                    app.estados.pop(number, None)
                    app.estados.pop(f"{number}_otros", None)
                    app.estados.pop(f"{number}_tienda", None)

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
            if estado_actual not in estados_funciones:
                mensaje = "Ha ocurrido un error. Por favor, inicia el flujo nuevamente. 😊"
                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                app.estados[number] = "inicio"
                return

            # Ejecutar la función correspondiente al estado actual
            estados_funciones[estado_actual]()

        except Exception as e:
            logging.error(f"Error en el flujo del chatbot para el usuario {number}: {e}")
            mensaje = "Ha ocurrido un error inesperado. Por favor, inicia el flujo nuevamente. 😊"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
            app.estados[number] = "inicio"

# Iniciar el chequeo de inactividad
start_inactivity_check()