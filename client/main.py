import streamlit as st
import requests
import time
import json
import hashlib
import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, serialization, hashes, asymmetric
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec

# Глобальные переменные для состояния
if "username" not in st.session_state:
    st.session_state.username = ""
if "server_ip" not in st.session_state:
    st.session_state.server_ip = ""
if "chat_name" not in st.session_state:
    st.session_state.chat_name = ""
if "chat_password" not in st.session_state:
    st.session_state.chat_password = ""
if "chat_hash" not in st.session_state:
    st.session_state.chat_hash = ""
if "connected" not in st.session_state:
    st.session_state.connected = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "users" not in st.session_state:
    st.session_state.users = []
if "ecdh_private_key" not in st.session_state:
    st.session_state.ecdh_private_key = None
if "ecdh_public_key" not in st.session_state:
    st.session_state.ecdh_public_key = None
if "session_key" not in st.session_state:
    st.session_state.session_key = None
if "is_creator" not in st.session_state:
    st.session_state.is_creator = False
if "last_timestamp" not in st.session_state:
    st.session_state.last_timestamp = 0.0
if "creator_ecdh_public_key" not in st.session_state:
    st.session_state.creator_ecdh_public_key = None
if "input_text" not in st.session_state:
    st.session_state.input_text = ""


def generate_ecdh_keys():
    """Генерирует пару ключей ECDH"""
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    pub_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    return private_key, pub_key_pem


def generate_session_key():
    """Генерирует случайный сессионный ключ для AES"""
    return os.urandom(32)  # 256-битный ключ для AES


def encrypt_message(text: str, key: bytes) -> str:
    """Шифрует сообщение с помощью AES"""
    iv = os.urandom(16)
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(text.encode('utf-8')) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode('utf-8')


def decrypt_message(ciphertext: str, key: bytes) -> str:
    """Расшифровывает сообщение с помощью AES"""
    full_ct = base64.b64decode(ciphertext)
    iv = full_ct[:16]
    ct = full_ct[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data.decode('utf-8')


def encrypt_with_shared_secret(data: bytes, shared_secret: bytes) -> str:
    """Шифрует данные с помощью AES, используя общий секрет"""
    key = hashlib.sha256(shared_secret).digest()
    iv = os.urandom(16)
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + ct).decode('utf-8')


def decrypt_with_shared_secret(ciphertext: str, shared_secret: bytes) -> bytes:
    """Расшифровывает данные с помощью AES, используя общий секрет"""
    key = hashlib.sha256(shared_secret).digest()
    full_ct = base64.b64decode(ciphertext)
    iv = full_ct[:16]
    ct = full_ct[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return unpadder.update(padded_data) + unpadder.finalize()


def get_public_keys():
    """Запрашивает публичные ключи ECDH всех пользователей в комнате"""
    if not st.session_state.connected or not st.session_state.is_creator:
        return {}
    try:
        response = requests.post(
            f"http://{st.session_state.server_ip}:8000/get_public_keys",
            json={
                "username": st.session_state.username,
                "chat_name": st.session_state.chat_name,
                "chat_hash": st.session_state.chat_hash
            }
        )
        if response.status_code == 200:
            return response.json().get("ecdh_public_keys", {})
        else:
            st.error(f"Ошибка получения публичных ключей: {response.json().get('detail', 'Неизвестная ошибка')}")
            return {}
    except Exception as e:
        st.error(f"Ошибка запроса публичных ключей: {e}")
        return {}


def register_user(server_ip: str, username: str, chat_name: str, chat_password: str) -> bool:
    """Регистрирует пользователя в комнате на сервере"""
    chat_hash = hashlib.sha256(chat_password.encode('utf-8')).hexdigest()
    ecdh_private_key, ecdh_pub_key = generate_ecdh_keys()

    try:
        response = requests.post(
            f"http://{server_ip}:8000/register",
            json={
                "username": username,
                "chat_name": chat_name,
                "chat_hash": chat_hash,
                "ecdh_public_key": ecdh_pub_key
            }
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.username = username
            st.session_state.server_ip = server_ip
            st.session_state.chat_name = chat_name
            st.session_state.chat_password = chat_password
            st.session_state.chat_hash = chat_hash
            st.session_state.ecdh_private_key = ecdh_private_key
            st.session_state.ecdh_public_key = ecdh_pub_key
            st.session_state.connected = True
            st.session_state.is_creator = data.get("is_creator", False)
            st.session_state.creator_ecdh_public_key = data.get("creator_ecdh_public_key")
            st.session_state.last_timestamp = time.time()

            # Если это создатель, генерируем сессионный ключ
            if st.session_state.is_creator:
                session_key = generate_session_key()
                st.session_state.session_key = session_key
                # Шифруем ключ для себя
                shared_secret = st.session_state.ecdh_private_key.exchange(
                    ec.ECDH(),
                    serialization.load_pem_public_key(st.session_state.ecdh_public_key.encode('utf-8'))
                )
                encrypted_session_key = encrypt_with_shared_secret(session_key, shared_secret)
                requests.post(
                    f"http://{server_ip}:8000/set_session_key",
                    json={
                        "username": username,
                        "chat_name": chat_name,
                        "chat_hash": chat_hash,
                        "target_username": username,
                        "encrypted_session_key": encrypted_session_key
                    }
                )
            # Если не создатель, пытаемся получить зашифрованный ключ
            if data.get("encrypted_session_key"):
                try:
                    creator_public_key = serialization.load_pem_public_key(
                        st.session_state.creator_ecdh_public_key.encode('utf-8')
                    )
                    shared_secret = st.session_state.ecdh_private_key.exchange(ec.ECDH(), creator_public_key)
                    session_key = decrypt_with_shared_secret(data["encrypted_session_key"], shared_secret)
                    st.session_state.session_key = session_key
                except Exception as e:
                    st.error(f"Ошибка расшифровки сессионного ключа: {e}")
                    return False

            return True
        else:
            st.error(f"Ошибка регистрации: {response.json().get('detail', 'Неизвестная ошибка')}")
            return False
    except Exception as e:
        st.error(f"Ошибка подключения: {e}")
        return False


def send_message(message: str):
    """Отправляет зашифрованное сообщение в комнату"""
    if not st.session_state.connected or not st.session_state.session_key:
        return
    ciphertext = encrypt_message(message, st.session_state.session_key)

    try:
        response = requests.post(
            f"http://{st.session_state.server_ip}:8000/send_message",
            json={
                "username": st.session_state.username,
                "chat_name": st.session_state.chat_name,
                "chat_hash": st.session_state.chat_hash,
                "ciphertext": ciphertext
            }
        )
        if response.status_code != 200:
            st.error(f"Ошибка отправки сообщения: {response.json().get('detail', 'Неизвестная ошибка')}")
    except Exception as e:
        st.error(f"Ошибка отправки: {e}")
        st.session_state.connected = False


def get_updates():
    """Получает обновления для комнаты и уведомляет создателя о новых пользователях"""
    if not st.session_state.connected:
        return
    try:
        response = requests.post(
            f"http://{st.session_state.server_ip}:8000/get_updates",
            json={
                "username": st.session_state.username,
                "chat_name": st.session_state.chat_name,
                "chat_hash": st.session_state.chat_hash,
                "last_timestamp": st.session_state.last_timestamp
            }
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.users = data["users"]
            st.session_state.messages.extend(data["messages"])
            st.session_state.last_timestamp = data["timestamp"]

            # Если это создатель, шифруем сессионный ключ для новых пользователей
            if st.session_state.is_creator and st.session_state.session_key:
                public_keys = get_public_keys()
                for user in st.session_state.users:
                    if user != st.session_state.username and user in public_keys:
                        try:
                            user_public_key = serialization.load_pem_public_key(
                                public_keys[user].encode('utf-8')
                            )
                            shared_secret = st.session_state.ecdh_private_key.exchange(ec.ECDH(), user_public_key)
                            encrypted_session_key = encrypt_with_shared_secret(st.session_state.session_key,
                                                                               shared_secret)
                            requests.post(
                                f"http://{st.session_state.server_ip}:8000/set_session_key",
                                json={
                                    "username": st.session_state.username,
                                    "chat_name": st.session_state.chat_name,
                                    "chat_hash": st.session_state.chat_hash,
                                    "target_username": user,
                                    "encrypted_session_key": encrypted_session_key
                                }
                            )
                        except Exception as e:
                            st.error(f"Ошибка шифрования ключа для {user}: {e}")

            # Проверяем, получили ли мы свой сессионный ключ
            if data.get("encrypted_session_key") and not st.session_state.session_key:
                try:
                    creator_public_key = serialization.load_pem_public_key(
                        st.session_state.creator_ecdh_public_key.encode('utf-8')
                    )
                    shared_secret = st.session_state.ecdh_private_key.exchange(ec.ECDH(), creator_public_key)
                    session_key = decrypt_with_shared_secret(data["encrypted_session_key"], shared_secret)
                    st.session_state.session_key = session_key
                except Exception as e:
                    st.error(f"Ошибка расшифровки сессионного ключа: {e}")
        else:
            st.error(f"Ошибка получения обновлений: {response.json().get('detail', 'Неизвестная ошибка')}")
            st.session_state.connected = False
    except Exception as e:
        st.error(f"Ошибка получения обновлений: {e}")
        st.session_state.connected = False


def main():
    st.title("Чат")

    # Форма подключения
    if not st.session_state.connected:
        with st.form("connect_form"):
            server_ip = st.text_input("IP сервера", value="127.0.0.1")
            username = st.text_input("Ваше имя")
            chat_name = st.text_input("ID чата")
            chat_password = st.text_input("Пароль", type="password")
            connect_button = st.form_submit_button("Подключиться")

            if connect_button and username and chat_name and chat_password:
                if register_user(server_ip, username, chat_name, chat_password):
                    st.success(f"Подключено как {username} в комнату {chat_name}")
                    st.rerun()
    else:
        # Периодическое обновление
        get_updates()

        # Отображение пользователей
        st.sidebar.title(f"Пользователи в комнате {st.session_state.chat_name}")
        for user in st.session_state.users:
            st.sidebar.write(user)

        # Отображение сообщений
        st.subheader("Сообщения")
        if st.session_state.session_key:
            for msg in st.session_state.messages:
                sender = msg['sender']
                try:
                    decrypted = decrypt_message(msg['ciphertext'], st.session_state.session_key)
                    st.write(f"**{sender}**: {decrypted}")
                except Exception as e:
                    st.write(f"**{sender}**: [Ошибка расшифровки: {e}]")
        else:
            st.error("Сессионный ключ не получен")

        # Форма отправки сообщения
        with st.form("message_form"):
            message = st.text_input("Введите сообщение", value=st.session_state.input_text)
            send_button = st.form_submit_button("Отправить")

            if send_button and message:
                send_message(message)
                st.session_state.input_text = ""
                st.rerun()

        # Автоматическое обновление каждые 2 секунды
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()