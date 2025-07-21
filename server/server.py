import socket
import threading

 # Коды ответов, запросов:
     # \x01 -- hello
     # \x02 -- accept
     # \x03 -- accept_hello

class Server:

    def __init__(self, host='127.0.0.1', port=23553, max_users=5) -> None:
        self.host = host
        self.port = port
        self.connections = set()
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind((host, port))
        self.tcp_socket.listen(max_users)

    def send_discover(self):
        print('sending discover')
        self.udp_socket.sendto(b'\x01', ('255.255.255.255', self.port))

    def accept_discover(self):
        print('accepting discover')
        addr, data = self.udp_socket.recvfrom(1024)
        if data == b'\x01':
            self.udp_socket.sendto(b'\x02', addr)
            self.connections.add(addr)
            addr, data = self.udp_socket.recvfrom(1024)
            if data != b'\x03':

        elif data == b'\x02':
            self.connections.add(addr)
            self.udp_socket.sendto(b'\x03', addr)
