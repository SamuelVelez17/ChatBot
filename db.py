import pyodbc
import requests
import json
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
import os
logging.basicConfig(filename='db.log', level=logging.DEBUG)

load_dotenv()
public = os.getenv("ippublica")
app_token = os.getenv("app_token")

# --------------------------------------GLPI--------------------------------------
def initSession():
    url = f"http://{public}/glpi/apirest.php/initSession/?app_token={app_token}"
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
# ---------------------------------------------------------------------------------

# --------------------------------------------BASE DE DATOS--------------------------------------------
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
                "ID": resultado[0],
                "NombreTienda": resultado[1],
                "Estado": resultado[2],
                "ResponsableDeTienda": resultado[3]
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
# -------------------------------------------------------------------------------------------------------

# --------------------------------------------TICKETS GLPI--------------------------------------------
def crearTicketYAsignarUsuario(nombre_tienda, responsable, estado, opcion_id, descripcion="", tienda_id=None):
    # Crear el ticket
    respuesta_crear_ticket = crearTicket(nombre_tienda, responsable, opcion_id, descripcion, tienda_id)

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

def crearTicket(nombre_tienda, responsable, opcion_id, descripcion="", tienda_id=None):
    url = f"http://{public}/glpi/apirest.php/Ticket/?app_token={app_token}&session_token={session_token}"
    logging.info(f"URL de creación de ticket: {url}")
    logging.info(f"Datos del ticket: nombre_tienda={nombre_tienda}, responsable={responsable}, tienda_id={tienda_id}, descripcion={descripcion}")

    # Agregar el ID de la tienda y el nombre del usuario a la descripción
    descripcion_completa = f"Soporte solicitado para la tienda: {nombre_tienda}, (ID: {tienda_id}). " \
                           f"Cuyo responsable es: {responsable}. " \
                           f"{descripcion}"

    payload = {
        "input": {
            "name": "Soporte",
            "content": descripcion_completa,
            "urgency": 3,
            "itilcategories_id": opcion_id
        }
    }

    try:
        response = requests.post(url, json=payload)
        logging.info(f"Respuesta de la API al crear el ticket: {response.text}")
        if response.status_code in [200, 201]:
            response_data = response.json()
            ticket_id = response_data.get("id")
            if ticket_id:
                return {"id": ticket_id, "message": "Ticket creado exitosamente."}
            else:
                return {"error": "No se pudo extraer el ID del ticket de la respuesta."}
        else:
            logging.error(f"Error al crear el ticket. Respuesta: {response.text}")
            return {"error": f"No pudimos crear el ticket"}
    except Exception as e:
        logging.error(f"Error al hacer la petición POST: {e}")
        return {"error": f"Error al hacer la petición POST: {e}"}

def solicitante(ticket_id, user_id=144):
    url = f"http://{public}/glpi/apirest.php/Ticket/{ticket_id}/Ticket_User/?app_token={app_token}&session_token={session_token}"
    
    payload = {
        "input": {
            "tickets_id": ticket_id,
            "users_id": user_id,
            "type": 1  # Tipo de usuario (1 para solicitante)
        }
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code in [200, 201]:  # Considera 201 como éxito también
            response_data = response.json()
            if "id" in response_data:  # Verifica si la respuesta contiene un ID
                logging.info(f"Usuario asignado correctamente al ticket {ticket_id}: {response_data}")
                return response_data
            else:
                error_msg = f"La respuesta no contiene un ID válido: {response_data}"
                logging.error(error_msg)
                return {"error": error_msg}
        else:
            error_msg = f"Error al asignar el usuario al ticket {ticket_id}. Respuesta: {response.text}"
            logging.error(error_msg)
            return {"error": error_msg}
    except Exception as e:
        error_msg = f"Error al hacer la petición POST al asignar usuario: {e}"
        logging.error(error_msg)
        return {"error": error_msg}

# Traer toda la información del TICKET
def consultarTicket(ticket_id):
    url = f"http://{public}/glpi/apirest.php/Ticket/{ticket_id}/?app_token={app_token}&session_token={session_token}"
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
    url = f"http://{public}/glpi/apirest.php/User/{users_id}?app_token={app_token}&session_token={session_token}"  # URL corregida
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
    url = f"http://{public}/glpi/apirest.php/Ticket/{ticket_id}/Ticket_User/?app_token={app_token}&session_token={session_token}"
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
    url = f"http://{public}/glpi/apirest.php/Ticket/{ticket_id}/?app_token={app_token}&session_token={session_token}"
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

# -------------------------------------------------------------------------------------------------------
# -------------------------------------------Funciones para manejar estados-------------------------------------------
def insertar_usuario(numero, estado, paso=None, tienda_id=None):
    conn = conectar()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO BOT_estado_usuario (numero, estado, paso, tienda_id, ultima_actividad) VALUES (?, ?, ?, ?, GETDATE())",
                (numero, estado, paso, tienda_id)
            )
            conn.commit()
        except Exception as e:
            logging.error(f"Error al insertar usuario: {e}")
        finally:
            conn.close()

def actualizar_estado(numero, estado, paso=None, tienda_id=None, nombre_usuario=None):
    conn = conectar()
    if conn:
        cursor = conn.cursor()
        try:
            # Construcción dinámica de la consulta
            query = "UPDATE BOT_estado_usuario SET estado = ?, ultima_actividad = GETDATE()"
            params = [estado]
            
            if paso is not None:
                query += ", paso = ?"
                params.append(paso)
            if tienda_id is not None:
                query += ", tienda_id = ?"
                params.append(tienda_id)
            if nombre_usuario is not None:
                query += ", nombre_usuario = ?"
                params.append(nombre_usuario)
                
            query += " WHERE numero = ?"
            params.append(numero)
            
            logging.info(f"Ejecutando query: {query} con params: {params}")
            cursor.execute(query, params)
            conn.commit()
            
            if cursor.rowcount == 0:
                # No se actualizó ningún registro, probar con INSERT
                logging.info("No se actualizó registro, intentando INSERT")
                insert_query = """
                    INSERT INTO BOT_estado_usuario 
                    (numero, estado, paso, tienda_id, nombre_usuario, ultima_actividad) 
                    VALUES (?, ?, ?, ?, ?, GETDATE())
                """
                insert_params = [numero, estado, paso, tienda_id, nombre_usuario]
                cursor.execute(insert_query, insert_params)
                conn.commit()
                logging.info("Insert realizado exitosamente")
            
            return True
        except Exception as e:
            logging.error(f"Error al actualizar estado: {str(e)}", exc_info=True)
            return False
        finally:
            conn.close()
    return False

def obtener_estado(numero):
    conn = conectar()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT estado, paso, tienda_id, nombre_usuario, ultima_actividad 
                FROM BOT_estado_usuario 
                WHERE numero = ?""", (numero,))
            row = cursor.fetchone()
            if row:
                return {
                    "estado": row.estado,
                    "paso": row.paso,
                    "tienda_id": row.tienda_id,
                    "nombre_usuario": row.nombre_usuario,
                    "ultima_actividad": row.ultima_actividad
                }
            return None
        except Exception as e:
            logging.error(f"Error al obtener estado: {str(e)}")
            return None
        finally:
            conn.close()
    return None

def eliminar_usuario(numero):
    conn = conectar()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM BOT_estado_usuario WHERE numero = ?", (numero,))
            conn.commit()
            logging.info(f"Usuario {numero} eliminado correctamente de la base de datos.")
        except Exception as e:
            logging.error(f"Error al eliminar usuario: {e}")
        finally:
            conn.close()

# Manejo de inactividad
def verificar_inactividad():
    while True:
        try:
            conn = conectar()  # Conectar a la base de datos
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT numero, ultima_actividad FROM BOT_estado_usuario")  # Obtener usuarios
                usuarios = cursor.fetchall()  # Recuperar todos los usuarios
                ahora = datetime.now()  # Obtener la hora actual
                for usuario in usuarios:
                    tiempo_inactivo = (ahora - usuario.ultima_actividad).total_seconds()  # Calcular tiempo inactivo
                    if tiempo_inactivo > 120:  # 2 minutos de inactividad
                        eliminar_usuario(usuario.numero)  # Eliminar usuario inactivo
                        logging.info(f"Usuario {usuario.numero} eliminado por inactividad.")  # Registrar en logs
                conn.close()  # Cerrar la conexión a la base de datos
        except Exception as e:
            logging.error(f"Error en verificar_inactividad: {e}")  # Registrar errores
        finally:
            time.sleep(60)  # Esperar 60 segundos antes de la siguiente verificación

# Iniciar el hilo de inactividad
def iniciar_hilo_inactividad():
    import threading
    hilo_inactividad = threading.Thread(target=verificar_inactividad, daemon=True)
    hilo_inactividad.start()
    logging.info("Hilo de inactividad iniciado.")