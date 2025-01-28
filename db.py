import pyodbc
import requests
import sett
import json

def verificarTienda(ID):
    url = "https://apitr.tiendaregistrada.com.co:5001/botTienda"  # Reemplaza con la URL de tu API
    params = {"ID": ID}
    print(f"Consultando la tienda con ID: {ID}")
    try:
        if url:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Levantar una excepción si la respuesta no es 200
            data = response.json()
            print(f"Tienda encontrada: {data}")
        else:
            print("No se encontró ninguna tienda con ese ID.")# Parsear la respuesta como JSON
            return data  # Retorna los datos recibidos de la API
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API: {e}")
        return None
    except Exception as e:
        print(f"Error al consultar la tienda: {e}")
        return e, 403
    return data  # Devuelve None si no se encuentra

def crearTicket(nombre_tienda, responsable, opcion_id, descripcion=""):
    url = "http://192.168.0.62:81/glpi/apirest.php/Ticket/?app_token={sett.app_token}&session_token={sett.session_token}"
    
    payload = {
        "input": {
            "name": "Soporte", 
            "content": f"Soporte solicitado para la tienda: {nombre_tienda}. Cuyo responsable es: {responsable}. {descripcion}",
            "urgency": 3,
            "itilcategories_id": opcion_id
        }
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code in [200, 201]:
            # Intentar parsear el JSON de respuesta
            try:
                response_data = response.json()
                ticket_id = response_data.get("id")
                if ticket_id:
                    return {"id": ticket_id, "message": "Ticket creado exitosamente."}
                else:
                    return {"error": "No se pudo extraer el ID del ticket de la respuesta."}
            except ValueError:
                # Error al parsear el JSON
                return {"error": f"No se pudo interpretar la respuesta del servidor: {response.text}"}
        else:
            return {"error": f"Error al crear el ticket. Respuesta: {response.text}"}
    except Exception as e:
        return {"error": f"Error al hacer la petición POST: {e}"}

def solicitante(ticket_id, user_id=144):
    url = f"http://192.168.0.62:81/glpi/apirest.php/Ticket/{ticket_id}/Ticket_User/?app_token={sett.app_token}&session_token={sett.session_token}"
    
    payload = {
        "input": {
            "tickets_id": ticket_id,
            "users_id": user_id
        }
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"Usuario asignado correctamente al ticket {ticket_id}: {response.text}")
            return response.json()
        else:
            error_msg = f"Error al asignar el usuario al ticket {ticket_id}. Respuesta: {response.text}"
            print(error_msg)
            return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error al hacer la petición POST al asignar usuario: {e}"
        print(error_msg)
        return {"error": error_msg}

def crearTicketYAsignarUsuario(nombre_tienda, responsable, estado, opcion_id, descripcion=""):
    # Crear el ticket
    respuesta_crear_ticket = crearTicket(nombre_tienda, responsable, opcion_id, descripcion)

    if "error" in respuesta_crear_ticket:
        return {"error": respuesta_crear_ticket["error"]}

    ticket_id = respuesta_crear_ticket.get("id")
    if not ticket_id:
        return {"error": "No se recibió un ID de ticket en la respuesta de la API."}

    # Asignar el usuario al ticket
    respuesta_asignacion = solicitante(ticket_id)
    if "error" in respuesta_asignacion:
        return {"message": f"✅ Hemos registrado tu solicitud. Tu número de ticket es: *{ticket_id}*."}

    return {"message": f"✅ Hemos registrado tu solicitud. Tu número de ticket es: {ticket_id}."}

# Traer toda la información del TICKET
def consultarTicket(ticket_id):
    url = f"http://192.168.0.62:81/glpi/apirest.php/Ticket/{ticket_id}/?app_token={sett.app_token}&session_token={sett.session_token}"
    params = {"id": ticket_id}
    print(f"Consultando el ticket con ID: {ticket_id}")
    try:
        if url:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Levantar una excepción si la respuesta no es 200
            data = response.json()
            print(f"Ticket encontrado: {data}")
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API: {e}")
        return None
    except Exception as e:
        print(f"Error al consultar el ticket: {e}")
        return 403
    return data  # Devuelve None si no se encuentra

# Trae toda la información dell usuario
def consultarUser(users_id):
    url = f"http://192.168.0.62:81/glpi/apirest.php/User/{users_id}/?app_token={sett.app_token}&session_token={sett.session_token}"
    params = {"ID": users_id}
    print(f"Consultando el usuario con ID: {users_id}")
    try:
        if url:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Levantar una excepción si la respuesta no es 200
            data = response.json()
            print(f"User encontrado: {data}")
            if data and isinstance(data, dict):
                return data.get('firstname', 'realname')
            else:
                print("No se encontró ningún usuario con ese ID")
                return None # Retorna los datos recibidos de la API
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API: {e}")
        return None
    except Exception as e:
        print(f"Error al consultar el usuario: {e}")
        return 403
    return data

def consultarAsignado(ticket_id):
    url = f"http://192.168.0.62:81/glpi/apirest.php/Ticket/{ticket_id}/Ticket_User/?app_token={sett.app_token}&session_token={sett.session_token}"
    params = {"ID": ticket_id}
    print(f"Consultando el ticket con ID: {ticket_id}")
    try:
        if url:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Levantar una excepción si la respuesta no es 200
            data = response.json()
            if len(data) > 1:
                user_position2 = data[1].get('users_id')
                print(f"users_id en la segunda posición: {user_position2}")
                return user_position2
            else:
                print("La lista no tiene suficientes elementos") # Retorna los datos recibidos de la API
    except Exception as e:
        print(f"Error al consultar el usuario: {e}")
        return e, 403
    return data

# Diccionario de estados
estados = {
    1: "Nuevo",
    2: "En curso (asignada)",
    3: "En curso (planificada)",
    4: "En espera",
    5: "Resuelto",
    6: "Cerrado",
    7: "Suprimido",
}

def consultarEstados(ticket_id):
    url = f"http://192.168.0.62:81/glpi/apirest.php/Ticket/{ticket_id}/?app_token={sett.app_token}&session_token={sett.session_token}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Verifica si hubo errores HTTP
        data = response.json()

        status_id = data.get('status')
        if status_id in estados:
            data['status'] = estados[status_id]
        else:
            print(f"Estado con ID '{status_id}' no encontrado.")
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API: {e}")
    except Exception as e:
        print(f"Error desconocido: {e}")
    return None

def consultarTicketConUsuario(ticket_id):
    ticket = consultarEstados(ticket_id)  # Consulta el ticket y su estado
    if not ticket:
        print("No se encontró información del ticket.")
        return None

    users_id = ticket.get('users_id_recipient')
    if users_id:
        user_name = consultarUser(users_id)
        ticket['users_id_recipient'] = user_name or "Usuario desconocido"

        # Consulta quién está asignado al ticket
        asignado_id = consultarAsignado(ticket_id)
        asignado = consultarUser(asignado_id)
        ticket['users_id_lastupdater'] = asignado or "No asignado"
        if ticket['status'] == "Nuevo" or ticket['users_id_recipient'] == "No asignado":
            mensaje_estado = (
                        "🏃🏽‍♂️En breve, un miembro de nuestro equipo comenzará a trabajar en tu solicitud. "
                        "Te enviaremos todas las actualizaciones del caso al correo electrónico registrado."
                    )
            return mensaje_estado
        else:
            print(f"Ticket actualizado: {ticket}")
            return ticket
    else:
        print("No se encontró el ID del usuario en el ticket.")

    return ticket

