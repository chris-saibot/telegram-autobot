import asyncio
import os
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOffline
import anthropic

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]
SESSION = os.environ.get("SESSION_STRING", "")

client = TelegramClient("session", API_ID, API_HASH)
ai = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

ANIMATIONS = [
    "🌑🌒🌓🌔🌕🌔🌓🌒🌑",
    "⚡💫✨🔥💥✨💫⚡",
    "🐱‍👤 печатает",
]

@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handler(event):
    me = await client.get_me()
    # Проверяем статус — если оффлайн, отвечаем
    sender = await event.get_sender()
    
    # Анимация "печатает"
    msg = await event.respond("💤")
    for frame in ["💤.", "💤..", "💤...", "🤖"]:
        await asyncio.sleep(0.5)
        await msg.edit(frame)

    # ИИ отвечает в твоём стиле
    response = ai.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        system="Ты — автоответчик пользователя Telegram. Отвечай коротко, по-дружески, как живой человек. Используй эмодзи иногда. Скажи что хозяин не в сети и вернётся позже.",
        messages=[{"role": "user", "content": event.raw_text}]
    )
    
    await msg.edit(response.content[0].text)

async def main():
    await client.start()
    print("Бот запущен! ✅")
    await client.run_until_disconnected()

asyncio.run(main())
