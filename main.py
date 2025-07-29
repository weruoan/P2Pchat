from server import Server



def chat():
    try:
        serverok = Server()
        serverok.start()
    except KeyboardInterrupt:
        print('Остановка программы')


if __name__ == "__main__":
    chat()
