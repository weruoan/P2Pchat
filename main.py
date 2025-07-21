import socket
import threading
import pickle
from server import Server

server = Server('0.0.0.0', 12345)
print(server)
server.send_discover()
server.accept_discover()
