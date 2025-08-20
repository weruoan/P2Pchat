from server import Server
import argparse

args = argparse.ArgumentParser()
args.add_argument('--udp-port', type=int, default=8080, help='Port to listen on')
# args.add_argument('--tcp-port', type=int, default=8081, help='Port to listen on')
args = args.parse_args()
# console = Console()


def main():
    try:
        serverok = Server(udp_port=args.udp_port)
        serverok.start()
    except KeyboardInterrupt:
        serverok.tcp_socket.close()
        serverok.udp_socket.close()
        print('Остановка программы')


if __name__ == "__main__":
    main()
