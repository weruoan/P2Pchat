from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time

app = FastAPI()

# Разрешаем CORS для доступа с клиентов Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище комнат: {chat_name: {"password": str, "clients": {username: last_active}, "messages": [{sender, text, timestamp}]}}
rooms: Dict[str, Dict] = {}


class UserRegistration(BaseModel):
    username: str
    chat_name: str
    chat_password: str


class Message(BaseModel):
    username: str
    chat_name: str
    chat_password: str
    text: str


class ChatUpdate(BaseModel):
    username: str
    chat_name: str
    chat_password: str
    last_timestamp: float


@app.post("/register")
async def register_user(user: UserRegistration):
    """Регистрирует пользователя в комнате"""
    # Если комната не существует, создаем её
    if user.chat_name not in rooms:
        rooms[user.chat_name] = {
            "password": user.chat_password,
            "clients": {},
            "messages": []
        }
    # Проверяем пароль
    if rooms[user.chat_name]["password"] != user.chat_password:
        raise HTTPException(status_code=403, detail="Неверный пароль комнаты")

    # Проверяем, не занят ли username в этой комнате
    if user.username in rooms[user.chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Пользователь уже существует в этой комнате")

    # Регистрируем пользователя
    rooms[user.chat_name]["clients"][user.username] = time.time()
    return {"status": "success", "username": user.username, "chat_name": user.chat_name}


@app.post("/send_message")
async def send_message(message: Message):
    """Сохраняет сообщение в комнате"""
    if message.chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if rooms[message.chat_name]["password"] != message.chat_password:
        raise HTTPException(status_code=403, detail="Неверный пароль комнаты")
    if message.username not in rooms[message.chat_name]["clients"]:
        raise HTTPException(status_code=400, detail="Пользователь не зарегистрирован в комнате")

    # Обновляем время активности пользователя
    rooms[message.chat_name]["clients"][message.username] = time.time()

    # Сохраняем сообщение
    rooms[message.chat_name]["messages"].append({
        "sender": message.username,
        "text": message.text,
        "timestamp": time.time()
    })
    return {"status": "success"}


@app.post("/get_updates")
async def get_updates(update: ChatUpdate):
    """Возвращает обновления для комнаты"""
    if update.chat_name not in rooms:
        raise HTTPException(status_code=404, detail="Комната не найдена")
    if rooms[update.chat_name]["password"] != update.chat_password:
        raise HTTPException(status_code=403, detail="Неверный пароль комнаты")
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

    # Получаем новые сообщения
    new_messages = [
        {"sender": msg["sender"], "text": msg["text"]}
        for msg in rooms[update.chat_name]["messages"]
        if msg["timestamp"] > update.last_timestamp
    ]

    return {
        "users": list(rooms[update.chat_name]["clients"].keys()),
        "messages": new_messages,
        "timestamp": current_time
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)