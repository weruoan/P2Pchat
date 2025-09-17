import socket
import time
from queue import Queue
from threading import Thread
from typing import Dict, Set, Tuple
from server.chat import Chat


class Server:
    def __init__(self, console, host: str = '0.0.0.0', udp_port: int = 8080, max_users: int = 5) -> None:
        """Initialize the server with UDP and TCP sockets for peer discovery and chat."""
        self.console = console
        self.host: str = host
        self.udp_port: int = udp_port
        self.tcp_port: int = udp_port + 1
        self.max_users: int = max_users
        self.scan_ports: list[int] = [8080, 8081, 8082, 8083, 8084]
        self.data_queue: Queue[Dict[Tuple[str, int], bytes]] = Queue()
        self.connections: Set[Tuple[str, int]] = set()
        self.approve_connect: str | None = None
        self.send_discover_flag: bool = True
        self.accept_discover_flag: bool = True

        # Initialize UDP socket for discovery
        self.udp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.bind((self.host, self.udp_port))

        # Initialize TCP socket for chat connections
        self.tcp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind((self.host, self.tcp_port))

    def send_discover(self, timeout: int = 15) -> None:
        """Periodically send discovery packets to broadcast address."""
        while self.send_discover_flag:
            for port in self.scan_ports:
                try:
                    self.udp_socket.sendto(b'\x01', ('255.255.255.255', port))
                except socket.error as e:
                    self.console.print(f"Ошибка отправки discovery: {e}")
            time.sleep(timeout)

    def accept_discover(self, timeout: int = 5) -> None:
        """Receive discovery packets and add them to the data queue."""
        self.udp_socket.settimeout(timeout)
        while self.accept_discover_flag:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                self.data_queue.put({addr: data})
            except socket.timeout:
                continue
            except socket.error as e:
                self.console.print(f"Ошибка получения discovery: {e}")

    def create_listen(self, addr: Tuple[str, int]) -> None:
        """Listen for incoming TCP connections and initiate chat."""
        try:
            self.udp_socket.sendto(b'\x02', addr)
            self.tcp_socket.listen(self.max_users)
            self.console.print(f"Ожидание подключения от {addr}...")
            client_socket, client_address = self.tcp_socket.accept()
            self.console.print(f"✅ Успешное подключение: {client_address}")
            self.send_discover_flag = False
            self.accept_discover_flag = False
            self.send_signal.join(timeout=1)
            self.accept_signal.join(timeout=1)
            Chat(self.console, client_socket)
        except socket.error as e:
            self.console.print(f"Ошибка при установке соединения: {e}")
        finally:
            self.cleanup()

    def create_connect(self, addr: Tuple[str, int], timer: int = 60) -> None:
        """Attempt to establish a TCP connection to the specified address."""
        try:
            now_time = 0
            while now_time < timer:
                if self.approve_connect == addr[0]:
                    self.tcp_socket.connect((addr[0], addr[1] + 1))
                    self.console.print(f"✅ Успешное подключение к {(addr[0], addr[1] + 1)}")
                    self.send_discover_flag = False
                    self.accept_discover_flag = False
                    self.send_signal.join(timeout=1)
                    self.accept_signal.join(timeout=1)
                    Chat(self.console, self.tcp_socket)
                    break
                else:
                    time.sleep(1)
                    now_time += 1
            else:
                self.console.print(f"⏰ Время ожидания подключения к {addr} истекло")
        except socket.error as e:
            self.console.print(f"Ошибка подключения к {addr}: {e}")
        finally:
            self.cleanup()

    def distributor(self) -> None:
        """Process incoming data from the queue and handle discovery or connection requests."""
        while True:
            try:
                packed_data = self.data_queue.get()
                addr, data = next(iter(packed_data.items()))
                if data is None:
                    continue
                elif data == b'\x01':  # Discovery packet
                    self.add_member(addr)
                    self.show_members()
                elif data == b'\x02':  # Connection request
                    self.console.print(f"📡 Запрос на подключение от {addr}")
                    waited_chat = Thread(target=self.create_connect, args=(addr,))
                    waited_chat.start()
            except Exception as e:
                self.console.print(f"Ошибка в distributor: {e}")

    def add_member(self, member: Tuple[str, int]) -> None:
        """Add a discovered member to the connections set."""
        self.connections.add(member)

    def show_members(self) -> None:
        """Display the list of discovered members in a formatted way."""
        self.console.clear()
        if not self.connections:
            self.console.print("📋 Список участников пуст")
        else:
            self.console.print("📋 Список участников:")
            for i, addr in enumerate(self.connections, 1):
                self.console.print(f"  {i}. {addr[0]}:{addr[1]}")

    def chat(self) -> None:
        """Prompt the user to select a member to connect to or approve a connection."""
        self.console.input_prompt = "Выберите участника для подключения (номер или /approve <IP>): "
        while True:
            self.show_members()
            choice = self.console.input()
            if choice == '-1':
                self.console.print("🚪 Выход из чата")
                break
            elif choice.startswith('/approve'):
                try:
                    self.approve_connect = choice.split()[1]
                    self.console.print(f"✅ Одобрено подключение от {self.approve_connect}")
                except IndexError:
                    self.console.print("❌ Ошибка: укажите IP после /approve")
            elif choice.isdigit() and 1 <= int(choice) <= len(self.connections):
                addr = list(self.connections)[int(choice) - 1]
                self.create_listen(addr)
                break
            else:
                self.console.print("❌ Неверный выбор, попробуйте снова")

    def cleanup(self) -> None:
        """Clean up sockets and threads."""
        try:
            self.udp_socket.close()
            self.tcp_socket.close()
        except socket.error:
            pass

    def start(self) -> None:
        """Start the server threads for discovery, data processing, and chat."""
        try:
            self.send_signal = Thread(target=self.send_discover, args=(5,), daemon=True)
            self.accept_signal = Thread(target=self.accept_discover, args=(1,), daemon=True)
            self.distributor_thread = Thread(target=self.distributor, daemon=True)
            self.chat_thread = Thread(target=self.chat, daemon=True)

            self.console.print("🚀 Сервер запущен")
            self.send_signal.start()
            self.accept_signal.start()
            self.distributor_thread.start()
            self.chat_thread.start()
            self.chat_thread.join()  # Keep the main thread alive until chat is done
        except Exception as e:
            self.console.print(f"Ошибка запуска сервера: {e}")
        finally:
            self.cleanup()