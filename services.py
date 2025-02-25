import requests
import json
import time
import db
import app
import threading
import logging
from dotenv import load_dotenv
import os
logging.basicConfig(filename='services.log', level=logging.DEBUG)
load_dotenv()
# Función para enviar mensaje de texto a través de WhatsApp
def enviar_Mensaje_whatsapp(data):
    try:
        whatsapp_token = os.getenv("whatsapp_token")
        whatsapp_url = os.getenv("whatsapp_url")
        headers = {'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + whatsapp_token}
        print("Se está enviando el mensaje")
        response = requests.post(whatsapp_url, 
                                headers=headers, 
                                data=data)
        
        if response.status_code == 200:
            print("Mensaje enviado exitosamente.")
            return 'mensaje enviado', 200
        else:
            print(f"Error al enviar mensaje: {response.status_code} - {response.text}")
            return 'error al enviar mensaje', response.status_code
    except Exception as e:
        print(f"Error al intentar enviar el mensaje: {e}")
        return (str(e)), 403

# Función para generar un mensaje de texto
def text_Message(number, text):
    data = json.dumps(
            {
                "messaging_product": "whatsapp",    
                "recipient_type": "individual",
                "to": number,
                "type": "text",
                "text": {
                    "body": text
                }
            }
    )
    print(f"Mensaje de texto generado")
    return data

user_timers = {}  # Almacena los temporizadores de los usuarios
INACTIVITY_TIME_LIMIT = 120  # 2 minutos de inactividad

# Diccionario global para almacenar los tiempos de los usuarios
def reset_inactivity_timer(number):
    # Cancela el temporizador anterior si existe
    if number in user_timers:
        user_timers[number].cancel()  # Cancela el temporizador anterior

    # Crea un nuevo temporizador para finalizar el chat después de INACTIVITY_TIME_LIMIT
    user_timers[number] = threading.Timer(INACTIVITY_TIME_LIMIT, finalizar_chat, args=(number,))
    user_timers[number].start()

    print(f"Temporizador de usuario {number} reiniciado")
    logging.info(f"Temporizador de usuario {number} reiniciado")

def finalizar_chat(number):
    if number in app.estados:  # Solo finaliza si el usuario está en un estado activo
        mensaje = "⏱ Has sido desconectado por inactividad. Si necesitas ayuda, vuelve a iniciar el chat."
        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
        
        # Limpiar el estado del usuario
        app.estados.pop(number, None)
        if f"{number}_nombre" in app.estados:
            app.estados.pop(f"{number}_nombre", None)
        if f"{number}_tienda" in app.estados:
            app.estados.pop(f"{number}_tienda", None)
        if f"{number}_otros" in app.estados:
            app.estados.pop(f"{number}_otros", None)
        
        # Elimina el temporizador del usuario
        if number in user_timers:
            del user_timers[number]

    print(f"Chat finalizado para el usuario {number} por inactividad")
    logging.info(f"Chat finalizado para el usuario {number} por inactividad")

# Función que obtiene el mensaje de WhatsApp (lo que ya tenías)
def obtener_Mensaje_whatsapp(message):
    if 'type' not in message:
        text = 'mensaje no reconocido'
        return text

    typeMessage = message['type']
    if typeMessage == 'text':
        text = message['text']['body']
    elif typeMessage == 'button':
        text = message['button']['text']
    elif typeMessage == 'interactive' and message['interactive']['type'] == 'list_reply':
        text = message['interactive']['list_reply']['title']
    elif typeMessage == 'interactive' and message['interactive']['type'] == 'button_reply':
        text = message['interactive']['button_reply']['title']
    else:
        print(f"Mensaje no procesado correctamente, tipo: {typeMessage}")
        text = 'mensaje no procesado'

    print(f"Texto procesado: Obtener mensaje")
    return text

def buttonReply_Message(number, options, body, footer, sedd, messageId):
    print(f"Generando opciones de botón para el número {number}.")
    buttons = []
    for i, option in enumerate(options):
        buttons.append(
            {
                "type": "reply",
                "reply": {
                    "id": sedd + "_btn_" + str(i+1),
                    "title": option
                }
            }
        )

    data = json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body
                },
                "footer": {
                    "text": footer
                },
                "action": {
                    "buttons": buttons
                }
            }
        }
    )
    return data

def listReply_Message(number, opciones, body, footer, sedd, messageId):
    print(f"Generando opciones de lista para el número {number}.")
    rows = []
    for id_opcion, nombre_opcion in opciones.items():
        rows.append(
            {
                "id": f"{sedd}_opt_{id_opcion}",  # ID único basado en la clave del diccionario
                "title": nombre_opcion
            }
        )

    data = json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": body
                },
                "body": {
                    "text": footer
                },
                "action": {
                    "button": "Ver opciones",
                    "sections": [
                        {
                            "title": "Opciones de soporte",
                            "rows": rows
                        }
                    ]
                }
            }
        }
    )
    return data

def administrar_chatbot(text, number, messageId, name):
        # Verificar si el usuario quiere finalizar la conversación
    if text.strip().lower() in ["fin", "finalizar"]:
        # Solo finalizar si el usuario está en un estado activo
        if number in app.estados:
            mensaje = "🥹 Hemos finalizado tu chat, hasta pronto."
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
            app.estados.pop(number, None)  # Reiniciar el estado del usuario
            if f"{number}_nombre" in app.estados:
                app.estados.pop(f"{number}_nombre", None)
            if f"{number}_tienda" in app.estados:
                app.estados.pop(f"{number}_tienda", None)
            if f"{number}_otros" in app.estados:
                app.estados.pop(f"{number}_otros", None)
            if number in user_timers:
                del user_timers[number]
            return
        else:
            # Si el usuario no está en un estado activo, ignorar el comando "finalizar"
            return
    
    reset_inactivity_timer(number)
    print(f"---------------------Inicio del flujo de chat para el número {number} con el mensaje: {text}")
    logging.info(f"Inicio del flujo de chat para el número {number} con el mensaje: {text}")
    estado_actual = app.estados.get(number, "inicio")
    print(f"----------------------Estado actual del usuario {number}: {estado_actual}")
    logging.info(f"Estado actual del usuario {number}: {estado_actual}")

    opciones_soporte = {
        "43": "Factura Mayor",
        "59": "Generar JSON Hiopos>KF",
        "44": "Borrar Hist Ventas HData",
        "41": "Gestionar Códigos Null",
        "42": "Borrado de Precios",
        "38": "Otro"
    }
    areas ={
        "1":"Captura", 
        "2":"Negocios/Consultoría", 
        "3":"Administración", 
        "4":"TI"
    }
    
    
    def estado_inicio():
        saludos = ["hola", "buenas", "buenos", "compa", "soporte", "ti", "ayuda", "necesito", "tienda", "id"]
        if any(saludo in text.lower() for saludo in saludos):
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
            mensaje = "📩 ¡Bienvenido al chat de soporte TI de Tienda Registrada! ¿Cómo podemos ayudarte hoy?"
            botones = ["Crear solicitud", "Consultar solicitud"]
            recordatorio = "⏰ Finalizaremos automáticamente el chat después de 2 minutos de inactividad. Para finalizar el chat, escribe 'Fin' o 'Finalizar'."
            enviar_Mensaje_whatsapp(text_Message(number, recordatorio))
            data = buttonReply_Message(number, botones, mensaje, "Selecciona una opción", "confirmacion", messageId)
            enviar_Mensaje_whatsapp(data)
            app.estados[number] = "esperando_confirmacion"
        else:
            mensaje = "👋🏽 Por favor, saluda antes de iniciar."
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
            
    def estado_esperando_confirmacion():
        texto_normalizado = text.strip().lower()
        if texto_normalizado == "crear solicitud":
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
            mensaje = "¿A qué área perteneces?"
            data = listReply_Message(number, areas, mensaje, "Selecciona una opción", "confirmacion", messageId)
            enviar_Mensaje_whatsapp(data)
            app.estados[number] = "esperando_seleccion_area"
        elif texto_normalizado == "consultar solicitud":
            mensaje = "¿Cuál es el número del ticket a consultar?"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
            app.estados[number] = "esperando_ticket"
        else:
            mensaje = "Por favor, selecciona una opción. 😊"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))

    def estado_esperando_ticket():
        if text.isdigit():
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
            ticket_id = text
            mensaje = "💬 Estamos buscando información relacionada con el número de ticket que nos proporcionaste. ¡En un momento regresamos contigo!"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
            
            # Consultar la información del ticket
            ticket = db.consultarTicketConUsuario(ticket_id)
            if ticket:
                print(f"----------------------------Entro al if ticket")
                logging.info(f"Ticket encontrado: {ticket}")
                if isinstance(ticket, dict):  # Verifica si ticket es un diccionario
                    numero_ticket = ticket.get('id', 'Ticket desconocido')
                elif isinstance(ticket, str): #Verifica si es un string
                    print(f"Error al consultar el ticket: {ticket}") #Imprime el mensaje de error
                    logging.error(f"Error al consultar el ticket: {ticket}") #Guarda el mensaje de error en el log
                    mensaje_estado = ticket #Asigna el mensaje de error a la variable mensaje_estado
                    return mensaje_estado #Retorna el mensaje de error
                else:
                    print("Error: La variable 'ticket' no es un diccionario ni un string.")
                    return "Error al consultar el ticket." #Retorna un mensaje de error
                responsable = ticket.get('users_id_recipient', 'Usuario desconocido')
                asignado = ticket.get('users_id_lastupdater', 'SIN ASIGNAR')  # Usar el nombre del usuario
                estado = ticket.get('status', 'SIN REVISAR')
                
                # Verificar si el ticket está "Nuevo" y sin asignar
                if estado == "Nuevo":
                    mensaje_estado = (
                            "🏃🏽‍♂️En breve, un miembro de nuestro equipo comenzará a trabajar en tu solicitud. "
                            "Te enviaremos todas las actualizaciones del caso al correo electrónico registrado."
                        )
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje_estado))
                        
                else:
                    # Enviar mensaje con los datos del ticket
                    app.estados[f"{number}_ticket"] = {
                        "id": numero_ticket,
                        "responsable": responsable,
                        "asignado": asignado,
                        "estado": estado
                    }
                    mensaje = (
                        f"El ticket *#{numero_ticket}* 🎫, creado por *{responsable}* 🙋🏻, "
                        f"fue asignado a *{asignado}* y se encuentra en estado *{estado}*."
                    )
                    enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                # Finalizar el chat
                mensaje2 = "🥹 Hemos finalizado tu chat, hasta pronto."
                enviar_Mensaje_whatsapp(text_Message(number, mensaje2))
                app.estados.pop(number, None)  # Reiniciar el estado del usuario
                if f"{number}_nombre" in app.estados:
                    app.estados.pop(f"{number}_nombre", None)
                if f"{number}_tienda" in app.estados:
                    app.estados.pop(f"{number}_tienda", None)
                if f"{number}_otros" in app.estados:
                    app.estados.pop(f"{number}_otros", None)
                if number in user_timers:
                    del user_timers[number]
                return
            else:
                # Mensaje si no se encuentra el ticket
                mensaje = "No hemos encontrado un ticket con ese ID ❌. Verifica el ID y envíalo nuevamente."
                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
        else:
            mensaje = "Envía un ID de ticket válido, un número"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))

    def estado_esperando_area():
        texto_normalizado = text.strip().lower()
        if texto_normalizado in ("negocios/consultoría", "administración", "ti"):
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
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
        logging.info(f"Estado actual del usuario {number}: {estado_actual}")
        nombre = text.strip()
        app.estados[f"{number}_nombre"] = nombre
        mensaje = f"📝 Ingresaste tu nombre como *{nombre}*, ¿Es correcto?"
        data = buttonReply_Message(number, ["Sí", "No"], mensaje, "Confirma tu selección", "confirmacion", messageId)
        enviar_Mensaje_whatsapp(data)
        app.estados[number] = "esperando_confirmacion_nombre"

    def estado_esperando_confirmacion_nombre():
        texto_normalizado = text.strip().lower()
        if texto_normalizado in ["sí", "si"]:
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
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
        logging.info(f"Estado actual del usuario {number}: {estado_actual}")
        descripcion = text.strip()
        nombre = app.estados.get(f"{number}_nombre", "Usuario desconocido")

        respuesta = db.crearTicketYAsignarUsuario(
            nombre_tienda="Oficina",
            responsable=nombre,
            estado="Nuevo",
            opcion_id=38,  # ID predeterminado para soporte "Oficina"
            descripcion=f"Soporte solicitado por: {nombre}. {descripcion}"
        )

        if "error" in respuesta:
            mensaje_error = f"Hubo un error al procesar tu solicitud: {respuesta['error']}"
            data = text_Message(number, mensaje_error)  # Define data aquí
            enviar_Mensaje_whatsapp(data)
        else:
            mensaje_exito = f"{respuesta['message']}"
            mensaje = "🥹 Hemos finalizado tu chat, hasta pronto."
            data = text_Message(number, mensaje_exito)  # Define data aquí
            data2 = text_Message(number, mensaje)  # Define data2 aquí
            enviar_Mensaje_whatsapp(data)
            enviar_Mensaje_whatsapp(data2)

        # Reiniciar el estado del usuario (esto va fuera del if/else)
        app.estados.pop(number, None)
        app.estados.pop(f"{number}_nombre", None)
        del user_timers[number]
        return # Asegúrate de que la función siempre tenga un retorno

    def estado_esperando_id():
        if text.isdigit():
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
            tienda_id = text
            mensaje = "💬 Estamos buscando información relacionada con el ID que nos proporcionaste. ¡En un momento regresamos contigo!"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))
            tienda = db.verificarTienda(tienda_id)
            if tienda:
                nombre_tienda = tienda.get('NombreTienda', 'Tienda desconocida')
                responsable = tienda.get('ResponsableDeTienda', 'Responsable desconocido')
                estado = tienda.get('Estado', 'Estado desconocido')
                # Guarda el ID de la tienda en app.estados
                app.estados[f"{number}_tienda"] = {
                    "nombre": nombre_tienda,
                    "tienda_id": tienda_id,  # Asegúrate de guardar el ID de la tienda
                    "responsable": responsable,
                    "estado": estado
                }
                mensaje = f"❗Has seleccionado 🏪 *{nombre_tienda}* con ID *{tienda_id}*, cuyo responsable es 🙋🏻 *{responsable}* y que se encuentra en estado *{estado}* al día de hoy. ¿Es correcto? 🤔"
                data = buttonReply_Message(number, ["Sí", "No"], mensaje, "Confirma tu selección", "confirmacion", messageId)
                enviar_Mensaje_whatsapp(data)
                app.estados[number] = "esperando_confirmacion_tienda"
            else:
                mensaje = "No hemos encontrado una tienda con ese ID ❌. Verifica el id y envíalo nuevamente"
                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
        else:
            mensaje = "Por favor, envía un ID de tienda válido (un número). 😊"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))

    def estado_esperando_confirmacion_tienda():
        texto_normalizado = text.strip().lower()
        if texto_normalizado in ["sí", "si"]:
            print(f"Usuario {number} ha confirmado la tienda.")
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
            app.estados[number] = "esperando_seleccion"  # Cambiar al estado correcto
            mensaje = "Por favor, elige una opción de soporte: 🙌🏻"
            data = listReply_Message(number, opciones_soporte, mensaje, "Selecciona una opción", "soporte", messageId)
            enviar_Mensaje_whatsapp(data)
        elif texto_normalizado == "no":
            print(f"Usuario {number} ha respondido que la tienda no es correcta.")
            logging.info(f"Estado actual del usuario {number}: {estado_actual}")
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
            tienda_id = tienda.get("tienda_id", "ID desconocido")  # Obtén el ID de la tienda
            if opcion_id == "38":  # "Otro"
                mensaje = "✉️ Describe tu solicitud, para que nuestro equipo de soporte pueda ayudarte."
                enviar_Mensaje_whatsapp(text_Message(number, mensaje))
                app.estados[number] = "esperando_descripcion"
                app.estados[f"{number}_otros"] = {
                    "nombre_tienda": nombre_tienda,
                    "responsable": responsable,
                    "opcion_id": opcion_id,
                    "estado": tienda.get("estado"),
                    "tienda_id": tienda_id  # Asegúrate de pasar el ID de la tienda
                }
            else:  # Opción específica (Factura Mayor, etc.)
                respuesta = db.crearTicketYAsignarUsuario(nombre_tienda, responsable, tienda.get("estado"), opcion_id, tienda_id=tienda_id)  # Pasa el ID de la tienda
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
            mensaje = "Opción de soporte no válida ❌. Selecciona del menú. "
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))

    def estado_esperando_descripcion():
        otros_datos = app.estados.get(f"{number}_otros", {})
        nombre_tienda = otros_datos.get("nombre_tienda", "Tienda desconocida")  
        responsable = otros_datos.get("responsable", "Responsable desconocido")
        estado = otros_datos.get("estado", "Estado desconocido")
        opcion_id = otros_datos.get("opcion_id", "38")
        tienda_id = otros_datos.get("tienda_id", "ID desconocido")
        descripcion = text.strip()

        respuesta = db.crearTicketYAsignarUsuario(nombre_tienda, responsable, estado, opcion_id, descripcion, tienda_id)
        if "error" in respuesta:
            mensaje_error = f"Error al procesar tu solicitud: {respuesta['error']}"
            enviar_Mensaje_whatsapp(text_Message(number, mensaje_error))
        else:
            mensaje_exito = f"{respuesta['message']}"
            mensaje = "🥹 Hemos finalizado tu chat, hasta pronto."
            enviar_Mensaje_whatsapp(text_Message(number, mensaje_exito))
            enviar_Mensaje_whatsapp(text_Message(number, mensaje))

        # Reiniciar el estado del usuario
        app.estados.pop(number, None)
        app.estados.pop(f"{number}_otros", None)
        app.estados.pop(f"{number}_tienda", None)
        del user_timers[number]

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
        "esperando_seleccion_area": estado_esperando_area,
        "esperando_descripcion": estado_esperando_descripcion,
        "esperando_ticket": estado_esperando_ticket
    }

    # Ejecutar la función correspondiente al estado actual
    if estado_actual in estados_funciones:
        estados_funciones[estado_actual]()
    else:
        mensaje = "Ha ocurrido un error. Por favor, inicia el flujo nuevamente. 😊"
        enviar_Mensaje_whatsapp(text_Message(number, mensaje))
        app.estados[number] = "inicio"



