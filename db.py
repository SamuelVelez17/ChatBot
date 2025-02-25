import pyodbc
import requests
import json
import logging
from dotenv import load_dotenv
import os
logging.basicConfig(filename='db.log', level=logging.DEBUG)

load_dotenv()
private = os.getenv("ipprivate")
app_token = os.getenv("app_token")

def initSession():
    url = f"http://{private}/glpi/apirest.php/initSession/?app_token={app_token}"
    logging.info(f"Iniciando sesión en la API de GLPI {url}")

    username = "botsoporte"
    password = "qwerty"
    if url:
        try:
            response = requests.get(url, auth=(username, password))
            response.raise_for_status()  # Lanza una excepción para códigos de estado HTTP 4xx o 5xx
            data= response.json()
            print(f"Token de sesión: {data}")
            logging.info(f"Token de sesión: {data}")
            session_token = data.get('session_token')
            return session_token
        except Exception as e:
            print(f"Error en la solicitud: {e}")
            logging.error(f"Error en la solicitud: {e}")
            return None
    else:
        print(f"No se encontró la URL de la API.")
        logging.error(f"No se encontró la URL de la API.")

session_token = initSession()
print(f"Token de sesión: {session_token}")
logging.info(f"Token de sesión: {session_token}")

def conectar():
    db_server = os.getenv("db_server")
    db_database = os.getenv("db_database")
    db_user = os.getenv("db_user")
    db_pwd = os.getenv("db_pwd")
    try:
        # Conexión a la base de datos
        conexion = pyodbc.connect(
            f"DRIVER={{SQL Server}};SERVER={db_server};DATABASE={db_database};UID={db_user};PWD={db_pwd}"
        )
        return conexion
    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None
    
def verificarTienda(ID):
    conexion = conectar()
    if not conexion:
        return None

    cursor = conexion.cursor()
    
    try:
        query = os.getenv("query")
        logging.info(f"Ejecutando SQL: {query} con ID={ID}")
        cursor.execute(query, (ID,))  
        resultado = cursor.fetchone()
       
        if resultado:
            response = {
                "NombreTienda": resultado[0],
                "Estado": resultado[1],
                "ResponsableDeTienda": resultado[2]
            }
            logging.info(f"Tienda encontrada: {response}")
            return response
        else:
            logging.warning("No se encontró ninguna tienda con ese ID.")
            return None
        
    except Exception as e:
        logging.error(f"Error al consultar la tienda: {e}")
        return None
    finally:
        cursor.close()
        conexion.close()

# POR SI SE LLEGA A UTILIZAR CONSULTA A API DE TIENDAS
# def verificarTienda(ID):
    # url = "http://apitr.tiendaregistrada.com.co:5001/botTienda" #localhost:5002  
    # params = {"ID": ID}
    # print(f"Consultando la tienda con ID: {ID}")
    # logging.info(f"Consultando la tienda con ID: {ID}")
    # try:
        # if url:
            # #response = requests.get(url, params=params)
            # response = requests.get(url, params = params, verify=False)
            # response.raise_for_status()  # Levantar una excepción si la respuesta no es 200
            # data = response.json()
            # print(f"Tienda encontrada: {data}")
            # logging.info(f"Tienda encontrada: {data}")
        # else:
            # print("No se encontró ninguna tienda con ese ID.")
            # logging.error("No se encontró ninguna tienda con ese ID.")
            # return data  # Retorna los datos recibidos de la API
    # except requests.exceptions.RequestException as e:
        # print(f"Error al llamar a la API: {e}")
        # logging.error(f"Error al llamar a la API: {e}")
        # return None
    # except Exception as e:
        # print(f"Error al consultar la tienda: {e}")
        # logging.error(f"Error al consultar la tienda: {e}")
        # return e, 403
    # return data 

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

def crearTicket(nombre_tienda, responsable, opcion_id, descripcion=""):
    url = f"http://{private}/glpi/apirest.php/Ticket/?app_token={app_token}&session_token={session_token}"
    print(f"URL de creación de ticket: {url}")
    logging.info(f"URL de creación de ticket: {url}")
    
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
            print(f"Error al crear el ticket. Respuesta: {response.text}")
            logging.error(f"Error al crear el ticket. Respuesta: {response.text}")
            return {"error": f"No pudimos crear el ticket"}
    except Exception as e:
        return {"error": f"Error al hacer la petición POST: {e}"}

def solicitante(ticket_id, user_id=144):
    url = f"http://{private}/glpi/apirest.php/Ticket/{ticket_id}/Ticket_User/?app_token={app_token}&session_token={session_token}"
    
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
            logging.info(f"Usuario asignado correctamente al ticket {ticket_id}: {response.text}")
            return response.json()
        else:
            error_msg = f"Error al asignar el usuario al ticket {ticket_id}. Respuesta: {response.text}"
            print(error_msg)
            logging.error(error_msg)
            return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error al hacer la petición POST al asignar usuario: {e}"
        print(error_msg)
        logging.error(error_msg)
        return {"error": error_msg}

# Traer toda la información del TICKET
def consultarTicket(ticket_id):
    url = f"http://{private}/glpi/apirest.php/Ticket/{ticket_id}/?app_token={app_token}&session_token={session_token}"
    params = {"id": ticket_id}
    print(f"Consultando el ticket con ID: {ticket_id}")
    logging.info(f"Consultando el ticket con ID: {ticket_id}")
    try:
        if url:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Levantar una excepción si la respuesta no es 200
            data = response.json()
            print(f"Ticket encontrado: {data}")
            logging.info(f"Ticket encontrado: {data}")
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API: {e}")
        logging.error(f"Error al llamar a la API: {e}")
        return None
    except Exception as e:
        print(f"Error al consultar el ticket: {e}")
        logging.error(f"Error al consultar el ticket: {e}")
        return 403
    return data  # Devuelve None si no se encuentra

# Trae toda la información del usuario
def consultarUser(users_id):
    url = f"http://{private}/glpi/apirest.php/User/{users_id}?app_token={app_token}&session_token={session_token}"  # URL corregida
    print(f"Consultando el usuario con ID: {users_id}")
    logging.info(f"Consultando el usuario con ID: {users_id}")
    try:
        response = requests.get(url)
        response.raise_for_status()  # Lanza una excepción para códigos de error 4xx o 5xx
        data = response.json()
        print(f"User encontrado: {data}")
        logging.info(f"User encontrado: {data}")
        return data.get('firstname') or data.get('realname') or "Usuario desconocido"
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API: {e}")
        logging.error(f"Error al llamar a la API: {e}")
        if response.status_code == 404: #Manejo de error 404
            return "Usuario no encontrado"
        return None  # Devuelve None en caso de otros errores de la API
    except Exception as e:
        print(f"Error al consultar el usuario: {e}")
        logging.error(f"Error al consultar el usuario: {e}")
        return None  # Devuelve None para otros errores

def consultarAsignado(ticket_id):
    url = f"http://{private}/glpi/apirest.php/Ticket/{ticket_id}/Ticket_User/?app_token={app_token}&session_token={session_token}"
    params = {"ID": ticket_id}
    print(f"Consultando el ticket con ID: {ticket_id}")
    logging.info(f"Consultando el ticket con ID: {ticket_id}")
    try:
        if url:
            response = requests.get(url, params=params)
            response.raise_for_status()  # Levantar una excepción si la respuesta no es 200
            data = response.json()
            if len(data) > 1:
                user_position2 = data[1].get('users_id')
                print(f"users_id en la segunda posición: {user_position2}")
                logging.info(f"users_id en la segunda posición: {user_position2}")
                return user_position2
            else:
                print("La lista no tiene suficientes elementos")
                logging.error("La lista no tiene suficientes elementos")
    except Exception as e:
        print(f"Error al consultar el usuario: {e}")
        logging.error(f"Error al consultar el usuario: {e}")
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
    url = f"http://{private}/glpi/apirest.php/Ticket/{ticket_id}/?app_token={app_token}&session_token={session_token}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Verifica si hubo errores HTTP
        data = response.json()
        status_id = data.get('status')
        if status_id in estados:
            data['status'] = estados[status_id]
        else:
            print(f"Estado con ID '{status_id}' no encontrado.")
            logging.error(f"Estado con ID '{status_id}' no encontrado.")
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a la API: {e}")
        logging.error(f"Error al llamar a la API: {e}")
    except Exception as e:
        print(f"Error desconocido: {e}")
        logging.error(f"Error desconocido: {e}")
    return None

def consultarTicketConUsuario(ticket_id):
    ticket = consultarEstados(ticket_id)  # Consulta el ticket y su estado
    if not ticket:
        print("No se encontró información del ticket.")
        logging.error("No se encontró información del ticket.")
        return None

    users_id = ticket.get('users_id_recipient')
    if users_id:
        user_name = consultarUser(users_id)
        ticket['users_id_recipient'] = user_name or "Usuario desconocido"

        # Consulta quién está asignado al ticket
        asignado_id = consultarAsignado(ticket_id)
        asignado = consultarUser(asignado_id)
        ticket['users_id_lastupdater'] = asignado or "No asignado"
        return ticket
    else:
        print("No se encontró el ID del usuario en el ticket.")
        logging.error("No se encontró el ID del usuario en el ticket.")

    return ticket

