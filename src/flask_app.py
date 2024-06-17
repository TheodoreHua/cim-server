import secrets

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, disconnect

from client import Client
from gvars import VERSION

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
socketio = SocketIO(app)
clients = {}

MOTD = "Welcome to the CIM server!"
DEFAULT_DATA = {"server_version": VERSION}


@app.route("/")
def index():
    return "A centralized chat server for CIM clients. This is not a web interface."


@app.route("/health")
def health():
    return "ok"


@app.route("/type")
def type_():
    return "server"


@app.route("/version")
def version():
    return VERSION


@app.route("/motd")
def motd():
    return MOTD


@app.route("/online")
def online():
    return jsonify([i.username for i in clients.values()])


@socketio.on("connect")
def handle_connect():
    print(f"Client {request.sid} connected")
    client_version = request.headers.get("client-version")
    username = request.headers.get("username")
    if client_version is None:
        emit(
            "connect_response",
            {**DEFAULT_DATA, "success": False, "flags": ["version_missing"]},
        )
        return disconnect()

    flags = []
    additional_data = {}

    if username is None:
        flags.append("username_missing")
        username = f"Anonymous-{secrets.token_hex(4)}"
    elif any(client.username == username for client in clients.values()):
        flags.append("username_taken")
        username = f"{username}-{secrets.token_hex(4)}"

    clients[request.sid] = Client(request.sid, client_version, username)
    emit(
        "connect_response",
        {
            **DEFAULT_DATA,
            "success": True,
            "motd": MOTD,
            "flags": flags,
            "username": username,
            **additional_data,
        },
    )
    emit(
        "connect_broadcast",
        {**DEFAULT_DATA, "username": username},
        broadcast=True,
        include_self=False,
    )


@socketio.on("message")
def handle_message(data):
    print(f"Client {request.sid} sent message: {data}")
    if request.sid not in clients:
        emit(
            "global_error",
            {
                **DEFAULT_DATA,
                "fatal": True,
                "type": "client_unrecognized",
                "message": "Client unrecognized.",
            },
        )
        return disconnect()
    emit(
        "message_broadcast",
        {
            **DEFAULT_DATA,
            "message": data["message"],
            "sender": clients[request.sid].username,
        },
        broadcast=True,
        include_self=True,
    )


@socketio.on("username_update")
def handle_update_username(data):
    print(f"Client {request.sid} updated username to: {data}")
    if request.sid not in clients:
        emit(
            "global_error",
            {
                **DEFAULT_DATA,
                "fatal": True,
                "type": "client_unrecognized",
                "message": "Client unrecognized.",
            },
        )
        return disconnect()
    client = clients[request.sid]
    emit(
        "username_update_broadcast",
        {**DEFAULT_DATA, "old": client.username, "new": data},
        broadcast=True,
        include_self=True,
    )
    client.username = data


@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client {request.sid} disconnected")
    if request.sid in clients:
        emit(
            "disconnect_broadcast",
            {**DEFAULT_DATA, "username": clients[request.sid].username},
            broadcast=True,
            include_self=False,
        )
        del clients[request.sid]


if __name__ == "__main__":
    socketio.run(app, debug=True)
