import logging
import argparse
from logging.handlers import RotatingFileHandler
from server import Server, Console
from datetime import datetime
import sys


# Настройка логгера
def setup_logger():
    # Создаем логгер
    logger = logging.getLogger('ServerApp')
    logger.setLevel(logging.DEBUG)

    # Форматтер для логов
    log_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Обработчик для файла с ротацией (максимум 5МБ, 3 резервные копии)
    file_handler = RotatingFileHandler(
        filename=f'server_{datetime.now().strftime("%Y%m%d")}.log',
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)

    # Обработчик для консоли с цветами
    class ColoredFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': '\033[94m',  # Синий
            'INFO': '\033[92m',  # Зеленый
            'WARNING': '\033[93m',  # Желтый
            'ERROR': '\033[91m',  # Красный
            'CRITICAL': '\033[95m'  # Фиолетовый
        }
        RESET = '\033[0m'

        def format(self, record):
            color = self.COLORS.get(record.levelname, '')
            message = super().format(record)
            return f"{color}{message}{self.RESET}"

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # Добавляем оба обработчика к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Парсер аргументов командной строки
parser = argparse.ArgumentParser(description='UDP/TCP Server')
parser.add_argument('--udp-port', type=int, default=8080, help='Port to listen on')
args = parser.parse_args()


def main():
    # Инициализация логгера
    logger = setup_logger()
    logger.info("Starting server application")

    try:
        console = Console()
        logger.debug("Console initialized")

        serverok = Server(console=console, udp_port=args.udp_port)
        logger.info(f"Server initialized on UDP port {args.udp_port}")

        serverok.start()
        logger.info("Server started successfully")

    except KeyboardInterrupt:
        logger.warning("Received KeyboardInterrupt, shutting down")
        serverok.tcp_socket.close()
        logger.debug("TCP socket closed")
        serverok.udp_socket.close()
        logger.debug("UDP socket closed")
        del console
        logger.info("Console object deleted")
        logger.info("Program stopped")

    except Exception as error:
        logger.error(f"An error occurred: {str(error)}", exc_info=True)
        logger.critical("Server stopped due to unexpected error")


if __name__ == "__main__":
    main()