import asyncio
import os
import uuid
from datetime import datetime, timezone

import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_API_URL = os.getenv("CHAT_API_URL", "http://chatbot:32000/api/v1/chat")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("Привет! Задайте ваш вопрос, и я постараюсь помочь.")


@dp.message()
async def handle_message(message: Message):
    if not message.text:
        return

    user_id = str(message.from_user.id)
    trace_id = str(uuid.uuid4())
    request_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Показываем что бот печатает
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                CHAT_API_URL,
                json={"text": message.text, "context": ""},
                headers={
                    "Content-Type": "application/json",
                    "x-trace-id": trace_id,
                    "x-request-time": request_time,
                    "x-source-name": "telegram",
                    "x-user-id": user_id,
                },
            )
            response.raise_for_status()
            data = response.json()
            answer = data.get("response", "Не удалось получить ответ.")
    except httpx.TimeoutException:
        answer = "Запрос занял слишком много времени. Попробуйте ещё раз."
    except Exception as e:
        answer = f"Произошла ошибка. Попробуйте позже."

    await message.answer(answer)


async def main():
    print(f"Starting Telegram bot... API: {CHAT_API_URL}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
