from operator import add
import socket
from time import sleep
from queue import Queue

 # Коды ответов, запросов:
     # \x01 -- hello
     # \x02 -- accept
     # \x03 -- accept_hello

class Server:

    def __init__(self, host='127.0.0.1', port=23553, max_users=5) -> None:
        self.host = host
        self.port = port
        self.addr = None
        self.data_queue = Queue()
        self.connections = set()
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind((host, port))
        self.udp_socket.bind((host, port))
        self.tcp_socket.listen(max_users)

    def send_discover(self, timeout=5):
        print('sending discover')
        self.udp_socket.sendto(b'\x01', ('255.255.255.255', self.port))

    def accept_discover(self):
        print('accepting discover')
        addr, data = self.udp_socket.recvfrom(1024)
        self.data_queue.put({addr: data})
        
    def add_member(self):
        print(self.data_queue)
        
    def show_members(self):
        print(self.connections)
