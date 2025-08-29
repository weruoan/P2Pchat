import socket
from typing import Dict
from queue import Queue
import os
from threading import Thread

class Chat:
    def __init__(self, console, client_socket: socket.socket):
        # os.system('cls' if os.name =='nt' else 'clear')
        self.console = console
        self.console.clear()
        self.console.input_prompt = 'Введите сообщение: '
        self.console.print('Чат инициализирован')
        self.client_socket = client_socket
        self.accept_messages_flag = True
        self.send_message_flag = True
        self.data_queue: Queue[Dict[tuple[str, int], bytes]] = Queue()
        # Thread(target=self.self.console.print_queue).start()
        Thread(target=self.send_message).start()
        Thread(target=self.accept_messages).start()
        # self.client_socket.sendall(b'hi')
        
    def accept_messages(self):
        while self.accept_messages_flag:
            data, addr = self.client_socket.recvfrom(1024)
            if data:
                self.data_queue.put({addr: data})
                self.console.print(f'{addr}: {data.decode()}')
            
    def send_message(self):
        while self.send_message_flag:
            message = self.console.input('Введите сообщение: ')
            self.console.print('Вы: {message}'.format(message=message))

            if message == rb'\quit':
                self.accept_messages_flag = False
                self.send_message_flag = False
                self.client_socket.close()
                break
            self.client_socket.sendall(message.encode())
        
    # def self.console.print_queue(self):
    #     while True:
    #         packed_data = self.data_queue.get()
    #         self.console.print(next(iter(packed_data.items())))