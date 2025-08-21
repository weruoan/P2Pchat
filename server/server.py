import socket
from queue import Queue
from typing import Dict
from threading import Thread
import time
from server.chat import Chat

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
        self.send_discover_flag = True
        self.accept_discover_flag = True
        


    def send_discover(self, timeout=15):
        while self.send_discover_flag:
            for port in self.scan_ports:
                self.udp_socket.sendto(b'\x01', ('255.255.255.255', port))
            time.sleep(timeout)



    def accept_discover(self, timeout=5):
        while self.accept_discover_flag:
            data, addr = self.udp_socket.recvfrom(1024)
            self.data_queue.put({addr: data})

    def create_listen(self, addr):
        self.udp_socket.sendto(b'\x02', addr)
        self.tcp_socket.listen(self.max_users)
        client_socket, client_address = self.tcp_socket.accept()
        print('Успешное подключение', client_address)
        self.send_discover_flag = False
        self.accept_discover_flag = False
        self.send_signal.join(timeout=1)
        self.accept_signal.join(timeout=1)
        Chat(client_socket)
        # approve = input(f'Входящее подключение от {client_address}, yes/no: ')
        # if approve == 'yes':
        #     Chat(client_socket)
        # else:
        #     client_socket.close()
            

    def create_connect(self, addr):
        # print(addr)
        approove = input(f'\nЗапрос на подключение от {addr}, yes/no:')
        if approove == 'yes':
            self.tcp_socket.connect((addr[0], addr[1]+1))
        else:
            return
        self.send_discover_flag = False
        self.accept_discover_flag = False
        self.send_signal.join(timeout=1)
        self.accept_signal.join(timeout=1)
        print('успешное подключение к ', (addr[0], addr[1]+1))
        Chat(self.tcp_socket)

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
        if name == '-1':
            return
        self.create_listen(list(self.connections)[int(name)])
        # print('print', int(name), list(self.connections)[int(name)])
    
    def start(self):
        self.send_signal = Thread(target=self.send_discover, args=(5,), daemon=True)
        self.accept_signal = Thread(target=self.accept_discover, args=(1,), daemon=True)
        self.distributor_thread = Thread(target=self.distributor, daemon=True)
        self.chat_thread = Thread(target=self.chat, daemon=True)
        self.send_signal.start()
        self.accept_signal.start()
        self.distributor_thread.start()
        self.chat_thread.start()
        # self.send_signal.join()
        self.accept_signal.join()
        self.distributor_thread.join()
        
