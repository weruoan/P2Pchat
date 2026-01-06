from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
import hashlib
import base64
import bcrypt
import json
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

# Хранилище комнат: {chat_name: {"password_hash": str, "session_keys": {username: encrypted_session_key}, "creator": str, "creator_ecdh_public_key": str, "clients": {username: last_active}, "ecdh_public_keys": {username: public_key}, "connections": {username: websocket}, "messages": [{sender, ciphertext, timestamp}]}}
rooms: Dict[str, Dict] = {}


async def _broadcast_users(room: Dict) -> None:
    payload = json.dumps({
        "type": "users",
        "users": list(room["clients"].keys())
    })
    dead_users = []
    for target_user, ws in room["connections"].items():
        try:
            await ws.send_text(payload)
        except Exception:
            dead_users.append(target_user)
    for dead in dead_users:
        room["connections"].pop(dead, None)


async def _send_key_request(room: Dict, target_username: str) -> None:
    creator = room.get("creator")
    if not creator:
        return
    creator_ws = room["connections"].get(creator)
    if not creator_ws:
        return
    public_key = room["ecdh_public_keys"].get(target_username)
    if not public_key:
        return
    await creator_ws.send_text(json.dumps({
        "type": "key_request",
        "target_username": target_username,
        "public_key": public_key
    }))


class UserRegistration(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    ecdh_public_key: str


class UserJoin(BaseModel):
    username: str
    chat_name: str
    chat_password: str
    ecdh_public_key: str

class Message(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    chat_password: str
    ciphertext: str


class ChatUpdate(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    chat_password: str
    last_timestamp: float


class SessionKeyUpdate(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    target_username: str
    encrypted_session_key: str


class SessionKeysBatchUpdate(BaseModel):
    username: str
    chat_name: str
    chat_hash: str
    encrypted_session_keys: Dict[str, str]


class PublicKeysRequest(BaseModel):
    username: str
    chat_name: str
    chat_hash: str

# class GetVerify(BaseModel):
#     username: str
#     chat_name: str

@app.post("/register")
async def register_room(user: UserRegistration):
    """Создаёт новую комнату и регистрирует создателя"""
    
    if user.chat_name in rooms:
        raise HTTPException(
            status_code=400,
            detail="Комната уже существует"
        )

    rooms[user.chat_name] = {
        "password_hash": user.chat_hash,
        "session_keys": {},
        "creator": user.username,
        "creator_ecdh_public_key": user.ecdh_public_key,
        "clients": {},
        "ecdh_public_keys": {},
        "connections": {},
        "messages": [],
        # "secrets": {}

    }

    rooms[user.chat_name]["clients"][user.username] = time.time()
    rooms[user.chat_name]["ecdh_public_keys"][user.username] = user.ecdh_public_key

    return {
        "status": "success",
        "username": user.username,
        "chat_name": user.chat_name,
        "is_creator": True,
        "creator_ecdh_public_key": user.ecdh_public_key,
        "encrypted_session_key": None
    }


@app.post("/join")
async def join_room(user: UserJoin):
    """Подключает пользователя к существующей комнате"""

    if user.chat_name not in rooms:
        raise HTTPException(
            status_code=404,
            detail="Комната не существует"
        )

    room = rooms[user.chat_name]
    if not bcrypt.checkpw(user.chat_password.encode('utf-8'), room["password_hash"].encode('utf-8')):
        raise HTTPException(
            status_code=403,
            detail="Неверный хэш пароля комнаты"
        )

    if user.username in room["clients"]:
        raise HTTPException(
            status_code=400,
            detail="Пользователь уже существует в этой комнате"
        )

    room["clients"][user.username] = time.time()
    room["ecdh_public_keys"][user.username] = user.ecdh_public_key

    return {
        "status": "success",
        "username": user.username,
        "chat_name": user.chat_name,
        "is_creator": False,
        "creator_ecdh_public_key": room["creator_ecdh_public_key"],
        "encrypted_session_key": room["session_keys"].get(user.username)
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
    if chat_hash != rooms[chat_name]["password_hash"]:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    if rooms[chat_name]["creator"] != username:
        raise HTTPException(status_code=403, detail="Только создатель может установить сессионный ключ")
    if target_username not in rooms[chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Целевой пользователь не зарегистрирован")

    rooms[chat_name]["session_keys"][target_username] = encrypted_session_key
    target_ws = rooms[chat_name]["connections"].get(target_username)
    if target_ws:
        await target_ws.send_text(json.dumps({
            "type": "session_key",
            "encrypted_session_key": encrypted_session_key
        }))
    return {"status": "success"}


@app.post("/set_session_keys")
async def set_session_keys(data: SessionKeysBatchUpdate):
    """Устанавливает пачку зашифрованных сессионных ключей (только для создателя)"""
    chat_name = data.chat_name
    chat_hash = data.chat_hash
    username = data.username

    if chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if chat_hash != rooms[chat_name]["password_hash"]:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    if rooms[chat_name]["creator"] != username:
        raise HTTPException(status_code=403, detail="Только создатель может установить сессионный ключ")

    for target_username, encrypted_session_key in data.encrypted_session_keys.items():
        if target_username not in rooms[chat_name]["clients"]:
            continue
        rooms[chat_name]["session_keys"][target_username] = encrypted_session_key
        target_ws = rooms[chat_name]["connections"].get(target_username)
        if target_ws:
            await target_ws.send_text(json.dumps({
                "type": "session_key",
                "encrypted_session_key": encrypted_session_key
            }))

    return {"status": "success"}


@app.post("/send_message")
async def send_message(message: Message):
    """Сохраняет зашифрованное сообщение в комнате"""
    if message.chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if message.chat_password:
        if not bcrypt.checkpw(message.chat_password.encode('utf-8'), rooms[message.chat_name]["password_hash"].encode('utf-8')):
            raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    else:
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
    if update.chat_password:
        if not bcrypt.checkpw(update.chat_password.encode('utf-8'), rooms[update.chat_name]["password_hash"].encode('utf-8')):
            raise HTTPException(status_code=403, detail="Неверный парольы комнаты")
    else:
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
        rooms[update.chat_name]["connections"].pop(user, None)

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
    """Возвращает публичные ключи ECDH всех пользователей в комнате (только для creator)"""
    if request.chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if rooms[request.chat_name]["password_hash"] != request.chat_hash:
        raise HTTPException(status_code=403, detail="Неверный хэш пароля комнаты")
    if request.username not in rooms[request.chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Пользователь не зарегистрирован в комнате")
    missing_users = [
        u for u in rooms[request.chat_name]["clients"].keys()
        if u not in rooms[request.chat_name]["session_keys"]
    ]
    return {
        "status": "success",
        "ecdh_public_keys": rooms[request.chat_name]["ecdh_public_keys"],
        "missing_session_keys": missing_users
    }


@app.websocket("/ws/{chat_name}/{username}")
async def websocket_chat(websocket: WebSocket, chat_name: str, username: str):
    await websocket.accept()
    if chat_name not in rooms:
        await websocket.close(code=1008)
        return

    room = rooms[chat_name]
    chat_password = websocket.query_params.get("chat_password", "")
    chat_hash = websocket.query_params.get("chat_hash", "")
    if chat_password:
        if not bcrypt.checkpw(chat_password.encode('utf-8'), room["password_hash"].encode('utf-8')):
            await websocket.close(code=1008)
            return
    else:
        if chat_hash != room["password_hash"]:
            await websocket.close(code=1008)
            return

    if username not in room["clients"]:
        await websocket.close(code=1008)
        return

    existing_ws = room["connections"].get(username)
    if existing_ws:
        try:
            await existing_ws.close(code=1001)
        except Exception:
            pass
    room["connections"][username] = websocket
    room["clients"][username] = time.time()
    await _broadcast_users(room)

    encrypted_session_key = room["session_keys"].get(username)
    if encrypted_session_key:
        await websocket.send_text(json.dumps({
            "type": "session_key",
            "encrypted_session_key": encrypted_session_key
        }))
    elif username == room.get("creator"):
        for user in room["clients"].keys():
            if user == username:
                continue
            if user not in room["session_keys"]:
                await _send_key_request(room, user)
    else:
        if username not in room["session_keys"]:
            await _send_key_request(room, username)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = data.get("type", "message")
            if msg_type == "set_session_key":
                if username != room.get("creator"):
                    continue
                target_username = data.get("target_username")
                encrypted_session_key = data.get("encrypted_session_key")
                if not target_username or not encrypted_session_key:
                    continue
                if target_username not in room["clients"]:
                    continue
                room["session_keys"][target_username] = encrypted_session_key
                target_ws = room["connections"].get(target_username)
                if target_ws:
                    await target_ws.send_text(json.dumps({
                        "type": "session_key",
                        "encrypted_session_key": encrypted_session_key
                    }))
                continue
            if msg_type == "request_key":
                target_username = data.get("target_username") or username
                if target_username in room["clients"] and target_username not in room["session_keys"]:
                    await _send_key_request(room, target_username)
                continue
            ciphertext = data.get("ciphertext")
            if not ciphertext:
                continue
            if username not in room["session_keys"]:
                continue

            room["clients"][username] = time.time()
            message = {"sender": username, "ciphertext": ciphertext, "timestamp": time.time()}
            room["messages"].append(message)

            dead_users = []
            for target_user, ws in room["connections"].items():
                try:
                    await ws.send_text(json.dumps({
                        "type": "message",
                        "sender": username,
                        "ciphertext": ciphertext,
                        "timestamp": message["timestamp"]
                    }))
                except Exception:
                    dead_users.append(target_user)

            for dead in dead_users:
                room["connections"].pop(dead, None)
    except WebSocketDisconnect:
        room["connections"].pop(username, None)
        room["clients"].pop(username, None)
        room["ecdh_public_keys"].pop(username, None)
        room["session_keys"].pop(username, None)
        await _broadcast_users(room)
    except Exception:
        room["connections"].pop(username, None)
        room["clients"].pop(username, None)
        room["ecdh_public_keys"].pop(username, None)
        room["session_keys"].pop(username, None)
        await _broadcast_users(room)

    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ssl_certfile='./certs/cert.pem', ssl_keyfile='./certs/key.pem')
