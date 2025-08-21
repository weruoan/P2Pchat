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
        self.accept_messages_flag = True
        self.send_message_flag = True
        self.data_queue: Queue[Dict[tuple[str, int], bytes]] = Queue()
        # Thread(target=self.print_queue).start()
        Thread(target=self.send_message).start()
        Thread(target=self.accept_messages).start()
        # self.client_socket.sendall(b'hi')
        
    def accept_messages(self):
        while self.accept_messages_flag:
            data, addr = self.client_socket.recvfrom(1024)
            self.data_queue.put({addr: data})
            print(data)
            
    def send_message(self):
        while self.send_message_flag:
            message = input('Введите сообщение: ').encode()
            if message == rb'\quit':
                self.accept_messages_flag = False
                self.send_message_flag = False
                self.client_socket.close()
                break
            self.client_socket.sendall(message)
        
    # def print_queue(self):
    #     while True:
    #         packed_data = self.data_queue.get()
    #         print(next(iter(packed_data.items())))