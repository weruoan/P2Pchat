from server import Server
from rich.console import Console

console = Console()


def main():
    try:
        serverok = Server()
        serverok.start()
        
    except KeyboardInterrupt:
        print('Остановка программы')


if __name__ == "__main__":
    main()
    