import socket
class Server:

    def __init__(self, host, port, max_users) -> None:
        self.host = host
        self.port = port
        self.connections = set()
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind((host, port))
        self.tcp_socket.listen(max_users)

    def send_discover(self):
        self.udp_socket.sendto(b'\x23\x44', ('255.255.255.255', self.port))

    def accept_discover(self):
        addr, data = self.udp_socket.recv(1024)
        if data == b'\x23\x44':
            