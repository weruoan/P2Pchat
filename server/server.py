import socket
from queue import Queue
from typing import Dict
from threading import Thread
import time
import curses
from server.chat import Chat
import locale

# Set locale to support UTF-8
locale.setlocale(locale.LC_ALL, '')

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
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.height, self.width = self.stdscr.getmaxyx()
        self.display_win = curses.newwin(self.height - 2, self.width, 0, 0)
        self.input_win = curses.newwin(1, self.width, self.height - 1, 0)
        self.display_win.scrollok(True)
        self.stdscr.refresh()
        self.display_win.refresh()
        self.input_win.refresh()

    def send_discover(self, timeout=15):
        while self.send_discover_flag:
            for port in self.scan_ports:
                self.udp_socket.sendto(b'\x01', ('255.255.255.255', port))
            time.sleep(timeout)

    def accept_discover(self, timeout=5):
        while self.accept_discover_flag:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                self.data_queue.put({addr: data})
            except:
                if not self.accept_discover_flag:
                    break

    def create_listen(self, addr):
        self.udp_socket.sendto(b'\x02', addr)
        self.tcp_socket.listen(self.max_users)
        client_socket, client_address = self.tcp_socket.accept()
        self.display_win.addstr(f"Успешное подключение от {client_address}\n")
        self.display_win.refresh()
        self.send_discover_flag = False
        self.accept_discover_flag = False
        self.send_signal.join(timeout=1)
        self.accept_signal.join(timeout=1)
        curses.endwin()
        Chat(client_socket)

    def create_connect(self, addr):
        self.display_win.addstr(f"\nЗапрос на подключение от {addr}\n")
        self.display_win.refresh()
        self.input_win.clear()
        self.input_win.addstr(0, 0, f"Подтвердить подключение от {addr}? (да/нет): ")
        self.input_win.refresh()
        response = ""
        while True:
            char = self.input_win.get_wch()
            if char == '\n':
                break
            elif char == 127 or char == curses.KEY_BACKSPACE:
                response = response[:-1]
                self.input_win.clear()
                self.input_win.addstr(0, 0, f"Подтвердить подключение от {addr}? (да/нет): " + response)
                self.input_win.refresh()
            elif isinstance(char, str):
                response += char
                self.input_win.clear()
                self.input_win.addstr(0, 0, f"Подтвердить подключение от {addr}? (да/нет): " + response)
                self.input_win.refresh()
        if response.lower() in ('да', 'yes'):
            self.tcp_socket.connect((addr[0], addr[1]+1))
            self.send_discover_flag = False
            self.accept_discover_flag = False
            self.send_signal.join(timeout=1)
            self.accept_signal.join(timeout=1)
            self.display_win.addstr(f"Успешное подключение к {(addr[0], addr[1]+1)}\n")
            self.display_win.refresh()
            curses.endwin()
            Chat(self.tcp_socket)
        else:
            return

    def distributor(self):
        while True:
            packed_data = self.data_queue.get()
            addr, data = next(iter(packed_data.items()))
            if data is None:
                continue
            elif data == b'\x01':
                self.add_member(addr)
                self.show_members()
            elif data == b'\x02':
                waited_chat = Thread(target=self.create_connect, args=(addr,))
                waited_chat.start()

    def add_member(self, member):
        self.connections.add(member)

    def show_members(self):
        self.display_win.clear()
        self.display_win.addstr("Доступные пользователи:\n")
        for i, member in enumerate(self.connections):
            self.display_win.addstr(f"{i}: {member}\n")
        self.display_win.refresh()

    def chat(self):
        while True:
            self.show_members()
            self.input_win.clear()
            self.input_win.addstr(0, 0, "Выберите к кому подключиться (-1 для выхода): ")
            self.input_win.refresh()
            selection = ""
            while True:
                char = self.input_win.get_wch()
                if char == '\n':
                    break
                elif char == 127 or char == curses.KEY_BACKSPACE:
                    selection = selection[:-1]
                    self.input_win.clear()
                    self.input_win.addstr(0, 0, "Выберите к кому подключиться (-1 для выхода): " + selection)
                    self.input_win.refresh()
                elif isinstance(char, str):
                    selection += char
                    self.input_win.clear()
                    self.input_win.addstr(0, 0, "Выберите к кому подключиться (-1 для выхода): " + selection)
                    self.input_win.refresh()
            if selection == '-1':
                self.send_discover_flag = False
                self.accept_discover_flag = False
                self.send_signal.join(timeout=1)
                self.accept_signal.join(timeout=1)
                curses.endwin()
                break
            try:
                index = int(selection)
                if 0 <= index < len(self.connections):
                    self.create_listen(list(self.connections)[index])
                    break
            except ValueError:
                self.display_win.addstr("Неверный ввод. Введите номер или -1.\n")
                self.display_win.refresh()

    def start(self):
        self.send_signal = Thread(target=self.send_discover, args=(5,), daemon=True)
        self.accept_signal = Thread(target=self.accept_discover, args=(1,), daemon=True)
        self.distributor_thread = Thread(target=self.distributor, daemon=True)
        self.chat_thread = Thread(target=self.chat, daemon=True)
        self.send_signal.start()
        self.accept_signal.start()
        self.distributor_thread.start()
        self.chat_thread.start()
        self.chat_thread.join()