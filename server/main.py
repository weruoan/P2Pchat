from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import padding, serialization, hashes, asymmetric

app = FastAPI()

# Разрешаем CORS для доступа с клиентов Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище комнат: {chat_name: {"password_hash": str, "session_keys": {username: encrypted_session_key}, "creator": str, "creator_ecdh_public_key": str, "clients": {username: last_active}, "ecdh_public_keys": {username: public_key}, "messages": [{sender, ciphertext, timestamp}]}}
rooms: Dict[str, Dict] = {}


class UserRegistration(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    ecdh_public_key: str


class Message(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    ciphertext: str


class ChatUpdate(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    last_timestamp: float


class SessionKeyUpdate(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    target_username: str
    encrypted_session_key: str


class PublicKeysRequest(BaseModel):
    username: str
    chat_name: str
    chat_hash: str


@app.post("/register")
async def register_user(user: UserRegistration):
    """Регистрирует пользователя в комнате"""
    is_creator = False
    # Если комната не существует, создаем её
    if user.chat_name not in rooms:
        is_creator = True
        rooms[user.chat_name] = {
            "password_hash": user.chat_hash,
            "session_keys": {},
            "creator": user.username,
            "creator_ecdh_public_key": user.ecdh_public_key,
            "clients": {},
            "ecdh_public_keys": {},
            "messages": []
        }
    # Проверяем хэш пароля
    if rooms[user.chat_name]["password_hash"] != user.chat_hash:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")

    # Проверяем, не занят ли username в этой комнате
    if user.username in rooms[user.chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Пользователь уже существует в этой комнате")

    # Регистрируем пользователя
    rooms[user.chat_name]["clients"][user.username] = time.time()
    rooms[user.chat_name]["ecdh_public_keys"][user.username] = user.ecdh_public_key

    # Возвращаем статус и публичный ключ создателя
    return {
        "status": "success",
        "username": user.username,
        "chat_name": user.chat_name,
        "is_creator": is_creator,
        "creator_ecdh_public_key": rooms[user.chat_name]["creator_ecdh_public_key"],
        "encrypted_session_key": rooms[user.chat_name]["session_keys"].get(user.username)
    }


@app.post("/set_session_key")
async def set_session_key(data: SessionKeyUpdate):
    """Устанавливает зашифрованный сессионный ключ для пользователя (только для создателя)"""
    chat_name = data.chat_name
    chat_hash = data.chat_hash
    username = data.username
    target_username = data.target_username
    encrypted_session_key = data.encrypted_session_key

    if chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if rooms[chat_name]["password_hash"] != chat_hash:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    if rooms[chat_name]["creator"] != username:
        raise HTTPException(status_code=403, detail="Только создатель может установить сессионный ключ")
    if target_username not in rooms[chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Целевой пользователь не зарегистрирован")

    rooms[chat_name]["session_keys"][target_username] = encrypted_session_key
    return {"status": "success"}


@app.post("/send_message")
async def send_message(message: Message):
    """Сохраняет зашифрованное сообщение в комнате"""
    if message.chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if rooms[message.chat_name]["password_hash"] != message.chat_hash:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    if message.username not in rooms[message.chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Пользователь не зарегистрирован в комнате")
    if message.username not in rooms[message.chat_name]["session_keys"]:
        raise HTTPException(status_code=400, detail="Сессионный ключ не установлен для пользователя")

    # Обновляем время активности пользователя
    rooms[message.chat_name]["clients"][message.username] = time.time()

    # Сохраняем сообщение
    rooms[message.chat_name]["messages"].append({
        "sender": message.username,
        "ciphertext": message.ciphertext,
        "timestamp": time.time()
    })
    return {"status": "success"}


@app.post("/get_updates")
async def get_updates(update: ChatUpdate):
    """Возвращает обновления для комнаты"""
    if update.chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if rooms[update.chat_name]["password_hash"] != update.chat_hash:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    if update.username not in rooms[update.chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Пользователь не зарегистрирован в комнате")

    # Обновляем время активности
    rooms[update.chat_name]["clients"][update.username] = time.time()

    # Удаляем неактивных пользователей (более 30 секунд без запросов)
    current_time = time.time()
    inactive_users = [
        u for u, t in rooms[update.chat_name]["clients"].items()
        if current_time - t > 30
    ]
    for user in inactive_users:
        rooms[update.chat_name]["clients"].pop(user, None)
        rooms[update.chat_name]["ecdh_public_keys"].pop(user, None)
        rooms[update.chat_name]["session_keys"].pop(user, None)

    # Получаем новые сообщения
    new_messages = [
        {"sender": msg["sender"], "ciphertext": msg["ciphertext"]}
        for msg in rooms[update.chat_name]["messages"]
        if msg["timestamp"] > update.last_timestamp
    ]

    return {
        "users": list(rooms[update.chat_name]["clients"].keys()),
        "timestamp": current_time,
        "messages": new_messages,
        "encrypted_session_key": rooms[update.chat_name]["session_keys"].get(update.username)
    }


@app.post("/get_public_keys")
async def get_public_keys(request: PublicKeysRequest):
    """Возвращает публичные ключи ECDH всех пользователей в комнате (только для тех, кто знает пароль)"""
    if request.chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if rooms[request.chat_name]["password_hash"] != request.chat_hash:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    if request.username not in rooms[request.chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Пользователь не зарегистрирован в комнате")

    return {
        "status": "success",
        "ecdh_public_keys": rooms[request.chat_name]["ecdh_public_keys"]
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)