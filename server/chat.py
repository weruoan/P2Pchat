import socket
from typing import Dict
from queue import Queue
import curses
from threading import Thread
import locale

# Set locale to support UTF-8
locale.setlocale(locale.LC_ALL, '')

class Chat:
    def __init__(self, client_socket: socket.socket):
        self.client_socket = client_socket
        self.accept_messages_flag = True
        self.send_message_flag = True
        self.data_queue: Queue[Dict[tuple[str, int], bytes]] = Queue()
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.height, self.width = self.stdscr.getmaxyx()
        self.chat_win = curses.newwin(self.height - 2, self.width, 0, 0)
        self.input_win = curses.newwin(1, self.width, self.height - 1, 0)
        self.chat_win.scrollok(True)
        self.stdscr.refresh()
        self.chat_win.refresh()
        self.input_win.refresh()
        Thread(target=self.accept_messages).start()
        Thread(target=self.send_message).start()

    def accept_messages(self):
        while self.accept_messages_flag:
            try:
                data, addr = self.client_socket.recvfrom(1024)
                self.data_queue.put({addr: data})
                try:
                    message = f"Sender {addr}: {data.decode('utf-8')}"
                    self.chat_win.addstr(message + "\n", curses.A_NORMAL)
                except UnicodeDecodeError:
                    self.chat_win.addstr(f"Sender {addr}: [Non-UTF-8 data]\n", curses.A_NORMAL)
                self.chat_win.refresh()
                self.input_win.refresh()
            except:
                if not self.accept_messages_flag:
                    break

    def send_message(self):
        while self.send_message_flag:
            try:
                self.input_win.clear()
                self.input_win.addstr(0, 0, "Введите сообщение: ")
                self.input_win.refresh()
                message = ""
                while True:
                    char = self.input_win.get_wch()  # Use get_wch for Unicode input
                    if char == '\n':  # Enter key
                        break
                    elif char == 127 or char == curses.KEY_BACKSPACE:  # Backspace
                        message = message[:-1]
                        self.input_win.clear()
                        self.input_win.addstr(0, 0, "Введите сообщение: " + message)
                        self.input_win.refresh()
                    elif isinstance(char, str):  # Handle Unicode characters
                        message += char
                        self.input_win.clear()
                        self.input_win.addstr(0, 0, "Введите сообщение: " + message)
                        self.input_win.refresh()
                message_bytes = message.encode('utf-8')
                if message_bytes == rb'\quit':
                    self.accept_messages_flag = False
                    self.send_message_flag = False
                    self.client_socket.close()
                    curses.nocbreak()
                    self.stdscr.keypad(False)
                    curses.echo()
                    curses.endwin()
                    break
                if message_bytes:
                    self.client_socket.sendall(message_bytes)
                    self.chat_win.addstr(f"You: {message}\n")
                    self.chat_win.refresh()
                    self.input_win.refresh()
            except:
                if not self.send_message_flag:
                    curses.nocbreak()
                    self.stdscr.keypad(False)
                    curses.echo()
                    curses.endwin()
                    break