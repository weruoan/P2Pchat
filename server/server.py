import socket
from queue import Queue
from typing import Dict
from server.chat import Chat
from threading import Thread
import time

# Chat()
# Коды ответов, запросов:
# \x01 -- hello
# после hello устанвливается tcp коннект между двумя клиентами

# Струткура сообщения
# Все сообщений до 1024 байт
# 1-ый байт -- код ответа (запроса)

class Server:
    def __init__(self, host='0.0.0.0', tcp_port=23553, udp_port=23554, max_users=5) -> None:
        self.scan_ports = [udp_port, 8080, 8081]
        self.host: str = host
        self.tcp_port: int = tcp_port
        self.udp_port: int = udp_port
        self.data_queue: Queue[Dict[tuple[str, int], bytes]] = Queue()
        self.connections: set[tuple[str, int]] = set()
        self.udp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.tcp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind((host, tcp_port))
        self.udp_socket.bind((host, udp_port))
        self.tcp_socket.listen(max_users)


    def send_discover(self, timeout=15):
        while True:
            # print('sending discover')
            for port in self.scan_ports:
                self.udp_socket.sendto(b'\x01', ('255.255.255.255', port))
            time.sleep(timeout)



    def accept_discover(self, timeout=5):
        while True:
            # print('accepting discover')
            data, addr = self.udp_socket.recvfrom(1024)
            self.data_queue.put({addr: data})

    def create_connect(self, addr):
        self.tcp_socket.connect(addr)


    def distributor(self):
        while True:
            packed_data = self.data_queue.get()
            addr, data = next(iter(packed_data.items()))
            # print('data:', data, addr)
            if data is None:
                continue
            elif data == b'\x01':
                self.add_member(addr)




    def add_member(self, member):
        self.connections.add(member)
        # print('members:', self.connections)

    def show_members(self):
        print(self.connections)
    
    def chat(self):
        print(*list(enumerate(list(self.connections))))
        name = 0
        try:
            name = int(input('Выбирите к кому подключаться: '))
        except ValueError:
            self.chat()
        self.create_connect(list(self.connections)[name])
        print(list(self.connections)[int(name)])
    
    def start(self):
        send_signal = Thread(target=self.send_discover, args=(5,), daemon=True)
        accept_signal = Thread(target=self.accept_discover, args=(1,), daemon=True)
        distributor = Thread(target=self.distributor, daemon=True)
        chat = Thread(target=self.chat, daemon=True)
        send_signal.start()
        accept_signal.start()
        distributor.start()
        chat.start()
        send_signal.join()
        accept_signal.join()
        distributor.join()
        
