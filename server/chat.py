import socket
from typing import Dict
from queue import Queue
import os
from threading import Thread

class Chat:
    def __init__(self, client_socket: socket.socket):
        os.system('cls' if os.name =='nt' else 'clear')
        print('Чат инициализирован')
        self.client_socket = client_socket
        self.accept_messagess_flag = True
        self.data_queue: Queue[Dict[tuple[str, int], bytes]] = Queue()
        Thread(target=self.print_queue).start()
        self.client_socket.sendall(b'hi')
        
    def accept_messagess(self):
        while self.accept_messagess_flag:
            data, addr = self.client_socket.recvfrom(1024)
            self.data_queue.put({addr: data})
    def print_queue(self):
        while True:
            packed_data = self.data_queue.get()
            print(next(iter(packed_data.items())))