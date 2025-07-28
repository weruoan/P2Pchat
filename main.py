from os import access
import socket
import threading
import time

from server import Server

def send_discover(timeout: int, server: Server):
    while True:
        server.send_discover()
        time.sleep(timeout)
        
def accept_discover(timeout: int, server: Server):
    while True:
        server.accept_discover()
        time.sleep(timeout)
    

def chat():
    server = Server('127.0.0.1', 12345)
    send_signal = threading.Thread(target=send_discover, args=(5,server))
    accept_signal = threading.Thread(target=accept_discover, args=(1, server))
    send_signal.daemon = True
    accept_signal.daemon = True
    try:
        send_signal.start()
        accept_signal.start()
        send_signal.join()
        accept_signal.join()
    except KeyboardInterrupt:
        print('Остановка программы')
    
    
    

if __name__ == "__main__":
    
    chat()
