# CIM Server
The server component of the CIM (Command [Line] Instant Messenger) project, counterpart to the [CIM Client](https://github.com/TheodoreHua/cim-client).

## Installation
- Have a Python 3 environment set up (recommended to use a version >= 3.8)
- Clone the repository
- Install the required packages with `pip install -r requirements.txt`
- Run the server with `python server.py` (or `python3 server.py`)
  - The default program is production-ready via gevent, but should be compatible with other WSGI servers 
  - The server will be running on `0.0.0.0:61824` by default
- You may need to allow the port through your firewall
