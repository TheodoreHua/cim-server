import re
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
LENGTH_LIMIT = 10_000  # characters in a message
USERNAME_REGEX = r"^[a-zA-Z0-9_-]{3,24}$"
USERNAME_STR_REQUIREMENTS = "Your username must be: 3-24 characters; containing only letters, numbers, underscores, and hyphens."
DEFAULT_DATA = {"server_version": VERSION}

debug = False


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
    if debug:
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
    elif not re.fullmatch(USERNAME_REGEX, username):
        flags.append("username_invalid")
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
            "length_limit": LENGTH_LIMIT,
            "flags": flags,
            "username": username,
            **additional_data,
        },
    )
    if (
        "username_invalid" in flags
    ):  # send username requirements if invalid -- sent after connect_response
        emit(
            "server_message",
            {
                **DEFAULT_DATA,
                "message": USERNAME_STR_REQUIREMENTS,
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
    if debug:
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
    if len(data["message"]) > LENGTH_LIMIT:
        emit(
            "server_message",
            {
                **DEFAULT_DATA,
                "message": f"Your message was too long to send, the limit is {LENGTH_LIMIT:,} characters.",
            },
        )
        return
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
    if debug:
        print(f"Client {request.sid} requested username update: {data}")
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
    if data is None:
        emit(
            "username_update_response",
            {
                **DEFAULT_DATA,
                "success": False,
                "flags": ["username_missing"],
            },
        )
        return
    if not re.fullmatch(USERNAME_REGEX, data):
        emit(
            "server_message",
            {
                **DEFAULT_DATA,
                "message": USERNAME_STR_REQUIREMENTS,
            },
        )
        emit(
            "username_update_response",
            {**DEFAULT_DATA, "success": False, "flags": ["username_invalid"]},
        )
        return
    if any(client.username == data for client in clients.values()):
        emit(
            "username_update_response",
            {**DEFAULT_DATA, "success": False, "flags": ["username_taken"]},
        )
        return

    emit(
        "username_update_response",
        {**DEFAULT_DATA, "success": True, "username": data},
    )
    emit(
        "username_update_broadcast",
        {**DEFAULT_DATA, "old": client.username, "new": data},
        broadcast=True,
        include_self=True,
    )
    client.username = data


@socketio.on("disconnect")
def handle_disconnect():
    if debug:
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
    import argparse

    parser = argparse.ArgumentParser(
        description="CIM (Command [Line] Instant Messenger) Server"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for Flask, and enable verbose logging for the server.",
    )

    parse = parser.parse_args()
    debug = parse.debug
    # TODO: Migrate to logging module

    # We are using gevent, so the default server is production-ready.
    # However, the user can still use a production WSGI server manually if they wish.
    socketio.run(app, port=61824, debug=debug, use_reloader=debug, log_output=debug)
