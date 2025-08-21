import socket
from queue import Queue
from typing import Dict
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
    def __init__(self, host='0.0.0.0', udp_port=8080, max_users=5) -> None:
        self.scan_ports = [8080, 8081, 8082, 8083, 8084]
        self.host: str = host
        self.udp_port: int = udp_port
        self.tcp_port: int = udp_port + 1
        self.max_users: int = max_users
        self.data_queue: Queue[Dict[tuple[str, int], bytes]] = Queue()
        self.connections: set[tuple[str, int]] = set()
        self.udp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.tcp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_socket.bind((self.host, self.udp_port))
        self.tcp_socket.bind((self.host, self.tcp_port))
        


    def send_discover(self, timeout=15):
        while True:
            for port in self.scan_ports:
                self.udp_socket.sendto(b'\x01', ('255.255.255.255', port))
            time.sleep(timeout)



    def accept_discover(self, timeout=5):
        while True:
            data, addr = self.udp_socket.recvfrom(1024)
            self.data_queue.put({addr: data})

    def create_listen(self, addr):
        self.udp_socket.sendto(b'\x02', addr)
        self.tcp_socket.listen(self.max_users)

    def create_connect(self, addr):
        print(addr)
        self.tcp_socket.connect((addr[0], addr[1]+1))
        print('успешное подключение к ', (addr[0], addr[1]+1))

    def distributor(self):
        while True:
            packed_data = self.data_queue.get()
            addr, data = next(iter(packed_data.items()))
            if data is None:
                continue
            elif data == b'\x01':
                self.add_member(addr)
            elif data == b'\x02':
                waited_chat = Thread(target=self.create_connect, args=(addr,))
                waited_chat.start()

    def add_member(self, member):
        self.connections.add(member)

    def show_members(self):
        print(self.connections)
    
    def chat(self):
        name = input('Выбирите к кому подключаться: ')
        while name == '':
            print(*list(enumerate(list(self.connections))), sep='\n')
            name = input('Выбирите к кому подключаться: ')
        self.create_listen(list(self.connections)[int(name)])
        print('print', int(name), list(self.connections)[int(name)])
    
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
        
