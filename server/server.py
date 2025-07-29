from operator import add
import socket
from time import sleep
from queue import Queue
from typing import Dict


# Коды ответов, запросов:
# \x01 -- hello
# \x02 -- accept
# \x03 -- accept_hello
# \x04 -- message

# Струткура сообщения
# Все сообщений до 1024 байт
# 1-ый байт -- код ответа (запроса)

class Server:

    def __init__(self, host='127.0.0.1', port=23553, max_users=5) -> None:
        self.host = host
        self.port = port
        self.addr = None
        self.data_queue: Queue[Dict[tuple[str, int], bytes]] = Queue()
        self.connections: set[tuple[str, int]] = set()
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
        data, addr = self.udp_socket.recvfrom(1024)
        self.data_queue.put({addr: data})

    def distributor(self):
        while True:
            packed_data = self.data_queue.get()
            addr, data = next(iter(packed_data.items()))
            print('data:', data, addr)
            if data is None:
                print(2)
                continue
            elif data == b'\x01':
                
                self.add_member(addr)

    def add_member(self, member):
        self.connections.add(member)
        print('members:', self.connections)

    def show_members(self):
        print(self.connections)
