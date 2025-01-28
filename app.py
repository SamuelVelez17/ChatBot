from flask import Flask, request
import sett 
import services

app = Flask(__name__)

@app.route('/bienvenido', methods=['GET'])
def  bienvenido():
    return 'Hola mundo bigdateros, desde Flask'

@app.route('/webhook', methods=['GET'])
def verificar_token():
    try:
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if token == sett.token and challenge is not None:
            return challenge
        else:
            return 'token incorrecto', 403
    except Exception as e:
        return e,403

estados = {}
@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    try:
        body = request.get_json()
        print(f"Mensaje recibido:")
        entry = body['entry'][0]
        changes = entry['changes'][0]
        value = changes['value']
        message = value['messages'][0]
        number = message['from']
        messageId = message['id']
        contacts = value['contacts'][0]
        name = contacts['profile']['name']
        text = services.obtener_Mensaje_whatsapp(message)

        print(f"Procesando mensaje del número: {number}, Nombre: {name}, Mensaje: {text}")

        services.administrar_chatbot(text, number, messageId, name)
        return 'enviado'

    except Exception as e:
        print(f"Error al recibir mensaje: {e}")
        return 'no enviado ' + str(e)

if __name__ == '__main__':
    app.run()