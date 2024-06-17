import secrets

from flask import Flask, request
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


@socketio.on("connect")
def handle_connect():
    print(f"Client {request.sid} connected")
    version = request.headers.get("client-version")
    username = request.headers.get("username")
    if version is None:
        emit(
            "connect_response",
            {**DEFAULT_DATA, "success": False, "flags": ["version_missing"]},
        )
        return disconnect()
    if username is None:
        emit(
            "connect_response",
            {**DEFAULT_DATA, "success": False, "flags": ["username_missing"]},
        )
        return disconnect()

    flags = []
    additional_data = {}

    if any(client.username == username for client in clients.values()):
        flags.append("username_taken")
        username = f"{username}-{secrets.token_hex(4)}"

    clients[request.sid] = Client(request.sid, version, username)
    emit(
        "connect_response",
        {
            **DEFAULT_DATA,
            "success": True,
            "flags": [],
            "username": username,
            "motd": MOTD,
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
