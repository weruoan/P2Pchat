import streamlit as st
import requests
from requests import exceptions as req_exc
import time
import json
import hashlib
import base64
import os
import bcrypt
import threading
import queue
from urllib.parse import urlencode, urlparse
import websocket
import ssl
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, serialization, hashes, asymmetric
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec

os.environ.setdefault('NO_PROXY', 'localhost,127.0.0.1,0.0.0.0')
os.environ.setdefault('no_proxy', 'localhost,127.0.0.1,0.0.0.0')

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
if "known_users" not in st.session_state:
    st.session_state.known_users = set()
if "ws_client" not in st.session_state:
    st.session_state.ws_client = None
if "ws_thread" not in st.session_state:
    st.session_state.ws_thread = None
if "ws_queue" not in st.session_state:
    st.session_state.ws_queue = queue.Queue()
if "ws_connected" not in st.session_state:
    st.session_state.ws_connected = False
if "ws_connected_event" not in st.session_state:
    st.session_state.ws_connected_event = threading.Event()
if "ws_connecting_event" not in st.session_state:
    st.session_state.ws_connecting_event = threading.Event()
if "ws_url" not in st.session_state:
    st.session_state.ws_url = ""
if "http_base_url" not in st.session_state:
    st.session_state.http_base_url = ""
if "key_request_sent" not in st.session_state:
    st.session_state.key_request_sent = False

def _get_host_and_scheme(server_ip: str) -> tuple[str, str]:
    raw = server_ip.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        return parsed.netloc, parsed.scheme
    host = raw if ":" in raw else f"{raw}:8000"
    return host, ""


def _candidate_http_base_urls(server_ip: str) -> list[str]:
    host, scheme = _get_host_and_scheme(server_ip)
    if scheme:
        return [f"{scheme}://{host}"]
    urls = []
    cached = st.session_state.http_base_url
    if cached:
        parsed = urlparse(cached)
        if parsed.netloc == host:
            urls.append(cached)
    for s in ["https", "http"]:
        url = f"{s}://{host}"
        if url not in urls:
            urls.append(url)
    return urls


def _post_with_fallback(path: str, payload: dict, server_ip: str) -> requests.Response:
    last_exc = None
    for base_url in _candidate_http_base_urls(server_ip):
        try:
            response = requests.post(
                f"{base_url}{path}",
                json=payload,
                verify=False
            )
            st.session_state.http_base_url = base_url
            return response
        except req_exc.RequestException as e:
            last_exc = e
            continue
    if last_exc:
        raise last_exc
    raise req_exc.ConnectionError("No candidate base URL")


def _post_register(endpoint: str, server_ip: str,username: str, chat_name: str, chat_password: str) -> bool:
    
    
    ecdh_private_key, ecdh_pub_key = generate_ecdh_keys()
    if endpoint == "register":
        st.session_state.chat_hash = bcrypt.hashpw(chat_password.encode("utf-8") , bcrypt.gensalt()).decode('utf-8')
        chat_hash = st.session_state.chat_hash
        response = _post_with_fallback(
            "/register",
            {
                "username": username,
                "chat_name": chat_name,
                "chat_hash": chat_hash,
                "ecdh_public_key": ecdh_pub_key
            },
            server_ip
        )
    elif endpoint == "join":
        response = _post_with_fallback(
            "/join",
            {
                "username": username,
                "chat_name": chat_name,
                "chat_password": chat_password,
                "ecdh_public_key": ecdh_pub_key
            },
            server_ip
        )
    try:
        data = response.json()
    except ValueError:
        data = None

    if response.status_code != 200:
        detail = data.get("detail", "Неизвестная ошибка") if isinstance(data, dict) else response.text
        st.error(f"Ошибка: {detail}, Response: {response}")
        return False

    if not isinstance(data, dict):
        st.error("Ошибка: сервер вернул некорректный ответ")
        return False

    # session_state
    st.session_state.update({
        "username": username,
        "server_ip": server_ip,
        "chat_name": chat_name,
        "chat_password": chat_password,
        "chat_hash": st.session_state.chat_hash,
        "ecdh_private_key": ecdh_private_key,
        "ecdh_public_key": ecdh_pub_key,
        "connected": True,
        "is_creator": data.get("is_creator", False),
        "creator_ecdh_public_key": data.get("creator_ecdh_public_key"),
        "last_timestamp": time.time(),
        "known_users": {username}
    })

    # 🔐 если создатель — генерируем session key
    if st.session_state.is_creator:
        session_key = generate_session_key()
        st.session_state.session_key = session_key

        creator_public_key = serialization.load_pem_public_key(ecdh_pub_key.encode())
        shared_secret = ecdh_private_key.exchange(ec.ECDH(), creator_public_key)
        encrypted_session_key = encrypt_with_shared_secret(session_key, shared_secret)
        set_session_keys_bulk({username: encrypted_session_key})

    # 🔓 если обычный участник — расшифровываем ключ
    elif data.get("encrypted_session_key"):
        creator_pub = serialization.load_pem_public_key(
            st.session_state.creator_ecdh_public_key.encode()
        )
        shared_secret = ecdh_private_key.exchange(ec.ECDH(), creator_pub)
        st.session_state.session_key = decrypt_with_shared_secret(
            data["encrypted_session_key"], shared_secret
        )

    return True


def create_room(server_ip, username, chat_name, chat_password) -> bool:
    return _post_register("register", server_ip, username, chat_name, chat_password)


def join_room(server_ip, username, chat_name, chat_password) -> bool:
    return _post_register("join", server_ip, username, chat_name, chat_password)


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
    """Creator запрашивает публичные ключи ECDH всех пользователей в комнате"""
    if not st.session_state.connected or not st.session_state.is_creator:
        return {}, []
    try:
        response = _post_with_fallback(
            "/get_public_keys",
            {
                "username": st.session_state.username,
                "chat_name": st.session_state.chat_name,
                "chat_hash": st.session_state.chat_hash
            },
            st.session_state.server_ip
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("ecdh_public_keys", {}), data.get("missing_session_keys", [])
        else:
            st.error(f"Ошибка получения публичных ключей: {response.json().get('detail', 'Неизвестная ошибка')}")
            return {}, []
    except Exception as e:
        st.error(f"Ошибка запроса публичных ключей: {e}")
        return {}, []


def set_session_keys_bulk(encrypted_session_keys: dict) -> None:
    """Creator отправляет пачку зашифрованных сессионных ключей на сервер"""
    if not encrypted_session_keys:
        return
    try:
        _post_with_fallback(
            "/set_session_keys",
            {
                "username": st.session_state.username,
                "chat_name": st.session_state.chat_name,
                "chat_hash": st.session_state.chat_hash,
                "encrypted_session_keys": encrypted_session_keys
            },
            st.session_state.server_ip
        )
    except Exception as e:
        st.error(f"Ошибка отправки пачки ключей: {e}")


def _make_ws_callbacks(
    connected_event: threading.Event,
    connecting_event: threading.Event,
    message_queue: queue.Queue
):
    def _ws_on_message(_, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        message_queue.put(data)

    def _ws_on_open(_):
        connected_event.set()
        connecting_event.clear()

    def _ws_on_close(_, __, ___):
        connected_event.clear()
        connecting_event.clear()

    return _ws_on_message, _ws_on_open, _ws_on_close


def _build_ws_url() -> str:
    if st.session_state.http_base_url:
        parsed = urlparse(st.session_state.http_base_url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        host = parsed.netloc
    else:
        raw = st.session_state.server_ip.strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            parsed = urlparse(raw)
            scheme = "wss" if parsed.scheme == "https" else "ws"
            host = parsed.netloc
        else:
            scheme = "ws"
            host = raw if ":" in raw else f"{raw}:8000"
    return f"{scheme}://{host}/ws/{st.session_state.chat_name}/{st.session_state.username}"


def _build_http_base_url(server_ip: str | None = None) -> str:
    raw = (server_ip or st.session_state.server_ip).strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw.rstrip("/")
    host = raw if ":" in raw else f"{raw}:8000"
    return f"http://{host}"


def start_ws_connection() -> None:
    if st.session_state.ws_connected_event.is_set():
        return
    if st.session_state.ws_connecting_event.is_set():
        ws_thread = st.session_state.ws_thread
        if ws_thread and ws_thread.is_alive():
            return
        st.session_state.ws_connecting_event.clear()
    if not st.session_state.connected:
        return
    query = {
        "chat_password": st.session_state.chat_password if not st.session_state.is_creator else "",
        "chat_hash": st.session_state.chat_hash if st.session_state.is_creator else ""
    }
    query = {k: v for k, v in query.items() if v}
    ws_url = _build_ws_url()
    if query:
        ws_url = f"{ws_url}?{urlencode(query)}"
    st.session_state.ws_connecting_event.set()
    on_message, on_open, on_close = _make_ws_callbacks(
        st.session_state.ws_connected_event,
        st.session_state.ws_connecting_event,
        st.session_state.ws_queue
    )
    if st.session_state.ws_url and st.session_state.ws_url != ws_url:
        close_ws_connection()
    st.session_state.ws_url = ws_url
    ws_app = websocket.WebSocketApp(
        ws_url,
        on_message=on_message,
        on_open=on_open,
        on_close=on_close,
    )
    st.session_state.ws_client = ws_app
    ws_thread = threading.Thread(
        target=ws_app.run_forever,
        kwargs={
            "ping_interval": 20,
            "ping_timeout": 10,
            "sslopt": {"cert_reqs": ssl.CERT_NONE}
        },
        daemon=True
    )
    st.session_state.ws_thread = ws_thread
    ws_thread.start()


def sync_ws_state() -> None:
    st.session_state.ws_connected = st.session_state.ws_connected_event.is_set()
    if st.session_state.ws_connected:
        st.session_state.ws_connecting_event.clear()


def close_ws_connection() -> None:
    ws_client = st.session_state.ws_client
    if ws_client:
        try:
            ws_client.close()
        except Exception:
            pass
    st.session_state.ws_client = None
    st.session_state.ws_thread = None
    st.session_state.ws_connected_event.clear()
    st.session_state.ws_connecting_event.clear()
    st.session_state.ws_url = ""


def ensure_ws_connected(timeout: float = 2.0) -> bool:
    if st.session_state.ws_connected_event.is_set():
        return True
    start_ws_connection()
    st.session_state.ws_connected_event.wait(timeout=timeout)
    sync_ws_state()
    return st.session_state.ws_connected


def drain_ws_messages() -> None:
    while not st.session_state.ws_queue.empty():
        msg = st.session_state.ws_queue.get()
        msg_type = msg.get("type")
        if msg_type == "users":
            users = msg.get("users", [])
            st.session_state.users = users
            st.session_state.known_users.update(users)
            continue
        if msg_type == "key_request" and st.session_state.is_creator and st.session_state.session_key:
            target_username = msg.get("target_username")
            public_key_pem = msg.get("public_key")
            if target_username and public_key_pem:
                try:
                    user_public_key = serialization.load_pem_public_key(
                        public_key_pem.encode('utf-8')
                    )
                    shared_secret = st.session_state.ecdh_private_key.exchange(ec.ECDH(), user_public_key)
                    encrypted_session_key = encrypt_with_shared_secret(
                        st.session_state.session_key, shared_secret
                    )
                    if ensure_ws_connected():
                        st.session_state.ws_client.send(json.dumps({
                            "type": "set_session_key",
                            "target_username": target_username,
                            "encrypted_session_key": encrypted_session_key
                        }))
                except Exception as e:
                    st.error(f"Ошибка шифрования ключа для {target_username}: {e}")
            continue
        if msg_type == "session_key" and not st.session_state.session_key:
            encrypted_session_key = msg.get("encrypted_session_key")
            if encrypted_session_key:
                try:
                    creator_public_key = serialization.load_pem_public_key(
                        st.session_state.creator_ecdh_public_key.encode('utf-8')
                    )
                    shared_secret = st.session_state.ecdh_private_key.exchange(ec.ECDH(), creator_public_key)
                    session_key = decrypt_with_shared_secret(encrypted_session_key, shared_secret)
                    st.session_state.session_key = session_key
                    st.session_state.key_request_sent = False
                except Exception as e:
                    st.error(f"Ошибка расшифровки сессионного ключа: {e}")
            continue
        if msg.get("sender") and msg.get("ciphertext"):
            st.session_state.messages.append({
                "sender": msg["sender"],
                "ciphertext": msg["ciphertext"]
            })


def send_message(message: str):
    """Отправляет зашифрованное сообщение в комнату"""
    if not st.session_state.connected or not st.session_state.session_key:
        return
    ciphertext = encrypt_message(message, st.session_state.session_key)

    try:
        if not st.session_state.ws_client or not ensure_ws_connected():
            st.error("WebSocket не подключен")
            return
        st.session_state.ws_client.send(json.dumps({"ciphertext": ciphertext}))
    except Exception as e:
        st.error(f"Ошибка отправки: {e}")
        st.session_state.connected = False


def main():
    st.title("Чат")
    if st.session_state.connected and not st.session_state.ws_client:
        st.session_state.messages = []
        st.session_state.users = []
        st.session_state.known_users = set()
        st.session_state.ws_queue = queue.Queue()

    # Форма подключения
    if not st.session_state.connected:
        if st.session_state.ws_client:
            close_ws_connection()
        tab_create, tab_join = st.tabs(["➕ Создать комнату", "➡️ Присоединиться"])

        with tab_create:
            st.subheader("Создание комнаты")
            server_ip = st.text_input("Server IP", key="c_server", value="127.0.0.1")
            username = st.text_input("Username", key="c_user")
            chat_name = st.text_input("Chat name", key="c_chat")
            chat_password = st.text_input("Chat password", type="password", key="c_pass")

            if st.button("Создать"):
                if create_room(server_ip, username, chat_name, chat_password):
                    st.success("Комната создана и вы подключены")
                    st.rerun()        

        with tab_join:
            st.subheader("Подключение к комнате")
            server_ip = st.text_input("Server IP", key="j_server", value="127.0.0.1")
            username = st.text_input("Username", key="j_user")
            chat_name = st.text_input("Chat name", key="j_chat")
            chat_password = st.text_input("Chat password", type="password", key="j_pass")

            if st.button("Подключиться"):
                if join_room(server_ip, username, chat_name, chat_password):
                    st.success(f"Подключено как {username} в комнату {chat_name}")
                    st.rerun()       
    else:
        start_ws_connection()
        sync_ws_state()
        drain_ws_messages()
        if not st.session_state.is_creator and not st.session_state.session_key and not st.session_state.key_request_sent:
            if ensure_ws_connected():
                st.session_state.ws_client.send(json.dumps({"type": "request_key"}))
                st.session_state.key_request_sent = True

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
            message = st.text_input("Введите сообщение", value='')
            send_button = st.form_submit_button("Отправить")
            st.session_state.input_text = ''
            if send_button and message:
                send_message(message)
                st.session_state.input_text = ""
                st.rerun()

        # Автоматическое обновление каждые 2 секунды
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()
