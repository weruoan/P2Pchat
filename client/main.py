import streamlit as st
import requests
import time
import json

# Глобальные переменные для состояния
if "username" not in st.session_state:
    st.session_state.username = ""
if "server_ip" not in st.session_state:
    st.session_state.server_ip = ""
if "chat_name" not in st.session_state:
    st.session_state.chat_name = ""
if "chat_password" not in st.session_state:
    st.session_state.chat_password = ""
if "connected" not in st.session_state:
    st.session_state.connected = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "users" not in st.session_state:
    st.session_state.users = []
if "last_timestamp" not in st.session_state:
    st.session_state.last_timestamp = 0.0

def register_user(server_ip: str, username: str, chat_name: str, chat_password: str) -> bool:
    """Регистрирует пользователя в комнате на сервере"""
    try:
        response = requests.post(
            f"http://{server_ip}:8000/register",
            json={"username": username, "chat_name": chat_name, "chat_password": chat_password}
        )
        if response.status_code == 200:
            st.session_state.username = username
            st.session_state.server_ip = server_ip
            st.session_state.chat_name = chat_name
            st.session_state.chat_password = chat_password
            st.session_state.connected = True
            st.session_state.last_timestamp = time.time()
            return True
        else:
            st.error(f"Ошибка регистрации: {response.json().get('detail', 'Неизвестная ошибка')}")
            return False
    except Exception as e:
        st.error(f"Ошибка подключения: {e}")
        return False

def send_message(message: str):
    """Отправляет сообщение в комнату"""
    if not st.session_state.connected:
        return
    try:
        response = requests.post(
            f"http://{st.session_state.server_ip}:8000/send_message",
            json={
                "username": st.session_state.username,
                "chat_name": st.session_state.chat_name,
                "chat_password": st.session_state.chat_password,
                "text": message
            }
        )
        if response.status_code != 200:
            st.error(f"Ошибка отправки сообщения: {response.json().get('detail', 'Неизвестная ошибка')}")
    except Exception as e:
        st.error(f"Ошибка отправки: {e}")
        st.session_state.connected = False

def get_updates():
    """Получает обновления для комнаты"""
    if not st.session_state.connected:
        return
    try:
        response = requests.post(
            f"http://{st.session_state.server_ip}:8000/get_updates",
            json={
                "username": st.session_state.username,
                "chat_name": st.session_state.chat_name,
                "chat_password": st.session_state.chat_password,
                "last_timestamp": st.session_state.last_timestamp
            }
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state.users = data["users"]
            st.session_state.messages.extend(data["messages"])
            st.session_state.last_timestamp = data["timestamp"]
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
        for msg in st.session_state.messages:
            st.write(f"**{msg['sender']}**: {msg['text']}")

        # Форма отправки сообщения
        with st.form("message_form"):
            message = st.text_input("Введите сообщение")
            send_button = st.form_submit_button("Отправить")

            if send_button and message:
                send_message(message)
                st.rerun()

        # Автоматическое обновление каждые 2 секунды
        time.sleep(2)
        st.rerun()

if __name__ == "__main__":
    main()